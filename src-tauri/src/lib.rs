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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(BackendState::default())
        .setup(|_app| {
            // En dev, on n'embarque pas le sidecar : on suppose que `start_backend.ps1`
            // est lancé séparément (hot reload uvicorn). En prod (release build), on
            // lance le binaire `backend` packagé par PyInstaller.
            #[cfg(not(debug_assertions))]
            {
                let sidecar = _app
                    .shell()
                    .sidecar("backend")
                    .expect("Sidecar `backend` introuvable. Build PyInstaller manqué ?")
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
                // On extrait le child du Mutex dans un bloc isolé pour que le MutexGuard
                // soit drop avant qu'on appelle .kill() — sinon le borrow checker rouspète
                // parce que `state` (qui borrow `app_handle`) dépasserait la durée de vie
                // du MutexGuard temporaire.
                let maybe_child = {
                    let state = app_handle.state::<BackendState>();
                    state.child.lock().unwrap().take()
                };
                if let Some(child) = maybe_child {
                    let _ = child.kill();
                }
            }
        });
}
