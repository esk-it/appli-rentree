// Empêche l'apparition d'une console Windows en plus de la fenêtre principale en release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    appli_rentree_lib::run()
}
