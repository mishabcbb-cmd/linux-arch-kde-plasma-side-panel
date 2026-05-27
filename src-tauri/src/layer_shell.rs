/**
 * src-tauri/src/layer_shell.rs — Native Wayland LayerShell via wayland-client.
 *
 * Uses wayland-client + wayland-protocols-wlr to create a layer surface
 * without any GTK dependency. This replaces QML LayerShell.Window.
 *
 * Protocol: wlr-layer-shell-unstable-v1 (zwlr_layer_shell_v1)
 */

use wayland_client::{
    protocol::{wl_compositor, wl_registry, wl_surface},
    Connection, Dispatch, QueueHandle,
};
use wayland_protocols_wlr::layer_shell::v1::client::{
    zwlr_layer_shell_v1::{self, Layer},
    zwlr_layer_surface_v1::{self, Anchor, KeyboardInteractivity},
};

/// LayerShell configuration.
#[derive(Debug, Clone)]
pub struct LayerShellConfig {
    pub edge: PanelEdge,
    pub layer: PanelLayer,
    pub width: u32,
    pub height: u32,
    pub exclusive_zone: i32,
    pub margin: i32,
    pub keyboard: bool,
}

impl Default for LayerShellConfig {
    fn default() -> Self {
        Self {
            edge: PanelEdge::Right,
            layer: PanelLayer::Top,
            width: 400,
            height: 0,
            exclusive_zone: 400,
            margin: 0,
            keyboard: true,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub enum PanelEdge { Left, Right, Top, Bottom }

#[derive(Debug, Clone, Copy)]
pub enum PanelLayer { Background, Bottom, Top, Overlay }

/// Wayland LayerShell state.
struct LayerShellState {
    config: LayerShellConfig,
    compositor: Option<wl_compositor::WlCompositor>,
    layer_shell: Option<zwlr_layer_shell_v1::ZwlrLayerShellV1>,
}

impl LayerShellState {
    fn new(config: LayerShellConfig) -> Self {
        Self {
            config,
            compositor: None,
            layer_shell: None,
        }
    }

    fn init(&mut self) {
        let conn = match Connection::connect_to_env() {
            Ok(c) => c,
            Err(e) => {
                log::error!("Wayland connection failed: {}", e);
                return;
            }
        };

        let mut event_queue = conn.new_event_queue();
        let qh = event_queue.handle();

        // Get registry using the proper wayland-client v0.31 API
        let _registry = wayland_client::globals::registry_queue_init::<LayerShellState>(&conn)
            .expect("Failed to init registry");

        // Roundtrip to get globals
        if let Err(e) = event_queue.roundtrip(self) {
            log::error!("Wayland roundtrip failed: {}", e);
            return;
        }

        // Create layer surface
        if let (Some(ref compositor), Some(ref layer_shell)) = (&self.compositor, &self.layer_shell) {
            let surface = compositor.create_surface(&qh, ());

            let layer_surface = layer_shell.get_layer_surface(
                &surface,
                None,
                match self.config.layer {
                    PanelLayer::Background => Layer::Background,
                    PanelLayer::Bottom => Layer::Bottom,
                    PanelLayer::Top => Layer::Top,
                    PanelLayer::Overlay => Layer::Overlay,
                },
                "ai-agent-panel".to_string(),
                &qh,
                (),
            );

            let anchor = match self.config.edge {
                PanelEdge::Left => Anchor::Left,
                PanelEdge::Right => Anchor::Right,
                PanelEdge::Top => Anchor::Top,
                PanelEdge::Bottom => Anchor::Bottom,
            };

            layer_surface.set_anchor(anchor);
            layer_surface.set_size(self.config.width, self.config.height);

            if self.config.exclusive_zone > 0 {
                layer_surface.set_exclusive_zone(self.config.exclusive_zone);
            }

            if self.config.margin != 0 {
                layer_surface.set_margin(self.config.margin, self.config.margin, self.config.margin, self.config.margin);
            }

            if self.config.keyboard {
                layer_surface.set_keyboard_interactivity(KeyboardInteractivity::OnDemand);
            }

            surface.commit();

            log::info!("LayerShell: anchor={:?}, layer={:?}, size={}x{}, exclusive_zone={}",
                self.config.edge, self.config.layer, self.config.width, self.config.height, self.config.exclusive_zone);

            // Event loop
            loop {
                if let Err(e) = event_queue.dispatch_pending(self) {
                    log::error!("Wayland dispatch error: {}", e);
                    break;
                }
                std::thread::sleep(std::time::Duration::from_millis(16));
            }
        } else {
            log::error!("Missing wl_compositor or zwlr_layer_shell_v1");
        }
    }
}

impl Dispatch<wl_registry::WlRegistry, ()> for LayerShellState {
    fn event(
        state: &mut Self,
        registry: &wl_registry::WlRegistry,
        event: wl_registry::Event,
        _: &(),
        _: &Connection,
        qh: &QueueHandle<Self>,
    ) {
        if let wl_registry::Event::Global { name, interface, version } = event {
            match interface.as_str() {
                "wl_compositor" => {
                    let compositor = registry.bind::<wl_compositor::WlCompositor, _, _>(
                        name, version.min(4), qh, (),
                    );
                    state.compositor = Some(compositor);
                    log::debug!("Bound wl_compositor v{}", version);
                }
                "zwlr_layer_shell_v1" => {
                    let layer_shell = registry.bind::<zwlr_layer_shell_v1::ZwlrLayerShellV1, _, _>(
                        name, version.min(4), qh, (),
                    );
                    state.layer_shell = Some(layer_shell);
                    log::debug!("Bound zwlr_layer_shell_v1 v{}", version);
                }
                _ => {}
            }
        }
    }
}

impl Dispatch<wl_compositor::WlCompositor, ()> for LayerShellState {
    fn event(_: &mut Self, _: &wl_compositor::WlCompositor, _: wl_compositor::Event, _: &(), _: &Connection, _: &QueueHandle<Self>) {}
}

impl Dispatch<wl_surface::WlSurface, ()> for LayerShellState {
    fn event(_: &mut Self, _: &wl_surface::WlSurface, _: wl_surface::Event, _: &(), _: &Connection, _: &QueueHandle<Self>) {}
}

impl Dispatch<zwlr_layer_shell_v1::ZwlrLayerShellV1, ()> for LayerShellState {
    fn event(_: &mut Self, _: &zwlr_layer_shell_v1::ZwlrLayerShellV1, _: zwlr_layer_shell_v1::Event, _: &(), _: &Connection, _: &QueueHandle<Self>) {}
}

impl Dispatch<zwlr_layer_surface_v1::ZwlrLayerSurfaceV1, ()> for LayerShellState {
    fn event(
        _: &mut Self,
        ls: &zwlr_layer_surface_v1::ZwlrLayerSurfaceV1,
        event: zwlr_layer_surface_v1::Event,
        _: &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
        if let zwlr_layer_surface_v1::Event::Configure { serial, width, height } = event {
            log::debug!("LayerShell configure: {}x{}", width, height);
            ls.ack_configure(serial);
        }
    }
}

/// Set up LayerShell for the Tauri window.
pub fn setup_layer_shell<R: tauri::Runtime>(
    _app: &tauri::AppHandle<R>,
    config: &LayerShellConfig,
) {
    if !is_wayland() {
        log::info!("Not on Wayland — LayerShell not applicable");
        return;
    }

    log::info!("Setting up native Wayland LayerShell: {:?}", config);

    let config = config.clone();
    std::thread::spawn(move || {
        let mut state = LayerShellState::new(config);
        state.init();
    });
}

fn is_wayland() -> bool {
    std::env::var("WAYLAND_DISPLAY").is_ok()
        || std::env::var("XDG_SESSION_TYPE")
            .map(|v| v == "wayland")
            .unwrap_or(false)
}

pub fn right_panel(width: u32) -> LayerShellConfig {
    LayerShellConfig {
        edge: PanelEdge::Right,
        layer: PanelLayer::Top,
        width,
        height: 0,
        exclusive_zone: width as i32,
        margin: 0,
        keyboard: true,
    }
}

pub fn left_panel(width: u32) -> LayerShellConfig {
    LayerShellConfig {
        edge: PanelEdge::Left,
        layer: PanelLayer::Top,
        width,
        height: 0,
        exclusive_zone: width as i32,
        margin: 0,
        keyboard: true,
    }
}
