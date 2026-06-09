use std::sync::Mutex;
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::CommandChild;

// Imports utilisés uniquement en prod (sidecar effectif)
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::process::CommandEvent;

/// État partagé : handle du processus enfant FastAPI (le sidecar Python).
/// Reste à `None` en dev (où on lance le backend manuellement avec `start_backend.ps1`).
#[derive(Default)]
struct BackendState {
    child: Mutex<Option<CommandChild>>,
}

const BACKEND_PORT: u16 = 8020;

/// Commande invocable depuis le frontend pour tuer proprement le sidecar.
///
/// Appelée par le code JS de mise à jour AVANT que l'installeur NSIS ne
/// remplace les fichiers — sinon NSIS échoue avec "Error opening file for
/// writing: appli-rentree-backend.exe".
#[tauri::command]
fn kill_backend(app: tauri::AppHandle) {
    let maybe_child = app
        .state::<BackendState>()
        .child
        .lock()
        .unwrap()
        .take();
    if let Some(child) = maybe_child {
        arret_propre_du_backend(child);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![kill_backend])
        .manage(BackendState::default())
        .setup(|_app| {
            // En dev, on n'embarque pas le sidecar : on suppose que `start_backend.ps1`
            // est lancé séparément (hot reload uvicorn). En prod (release build), on
            // lance le binaire `backend` packagé par PyInstaller.
            #[cfg(not(debug_assertions))]
            {
                let sidecar = _app
                    .shell()
                    .sidecar("appli-rentree-backend")
                    .expect("Sidecar `appli-rentree-backend` introuvable. Build PyInstaller manqué ?")
                    .args(["--port", &BACKEND_PORT.to_string()]);

                let (mut rx, child) = sidecar
                    .spawn()
                    .expect("Échec du démarrage du backend FastAPI");

                let state = _app.state::<BackendState>();
                *state.child.lock().unwrap() = Some(child);

                tauri::async_runtime::spawn(async move {
                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Stdout(line) => {
                                println!("[backend] {}", String::from_utf8_lossy(&line));
                            }
                            CommandEvent::Stderr(line) => {
                                eprintln!("[backend] {}", String::from_utf8_lossy(&line));
                            }
                            CommandEvent::Error(err) => {
                                eprintln!("[backend] erreur: {}", err);
                            }
                            CommandEvent::Terminated(payload) => {
                                eprintln!("[backend] terminé : {:?}", payload);
                                break;
                            }
                            _ => {}
                        }
                    }
                });
            }

            #[cfg(debug_assertions)]
            {
                println!(
                    "[tauri] Mode dev : le backend doit être lancé séparément (start_backend.ps1) sur le port {}",
                    BACKEND_PORT
                );
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Erreur de construction de l'application Tauri")
        .run(|app_handle, event| {
            if let RunEvent::ExitRequested { .. } = event {
                let maybe_child = app_handle
                    .state::<BackendState>()
                    .child
                    .lock()
                    .unwrap()
                    .take();
                if let Some(child) = maybe_child {
                    arret_propre_du_backend(child);
                }
            }
        });
}

/// Termine proprement le sidecar Python.
///
/// PyInstaller bundle `appli-rentree-backend.exe` comme bootloader qui lance
/// Python en sous-processus. Un simple `child.kill()` ne tue QUE le bootloader,
/// pas le vrai uvicorn → le binaire reste en mémoire avec le port 8020 occupé,
/// bloquant la prochaine installation/mise à jour.
///
/// Solution Windows : `taskkill /F /T /PID <pid>` pour tuer l'arbre complet.
fn arret_propre_du_backend(child: tauri_plugin_shell::process::CommandChild) {
    let pid = child.pid();

    // 1. Tente l'arrêt propre via l'endpoint /api/shutdown (timeout court).
    //    Le backend fait os._exit(0) après un petit délai, ce qui libère le port.
    std::thread::spawn(|| {
        if let Ok(client) = reqwest::blocking::Client::builder()
            .timeout(std::time::Duration::from_millis(300))
            .build()
        {
            let _ = client.post("http://127.0.0.1:8020/api/shutdown").send();
        }
    });
    // Laisse 300 ms au backend pour faire son os._exit(0)
    std::thread::sleep(std::time::Duration::from_millis(300));

    // 2. Force-kill du process ET de ses enfants (le vrai Python derrière
    //    le bootloader PyInstaller).
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        // CREATE_NO_WINDOW : empêche le flash d'une fenêtre CMD quand on lance
        // taskkill depuis notre app GUI. Sans ce flag, Windows ouvre une console
        // qui clignote brièvement à la fermeture.
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        let _ = std::process::Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
        // Au cas où taskkill aurait raté quelque chose
        let _ = child.kill();
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = pid; // évite warning unused
        let _ = child.kill();
    }
}
