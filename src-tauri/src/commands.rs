use serde::Serialize;

#[derive(Serialize)]
pub struct Response {
    pub message: String,
}

#[tauri::command]
pub async fn greet(name: &str) -> Response {
    Response {
        message: format!("Hello, {}!", name),
    }
}
