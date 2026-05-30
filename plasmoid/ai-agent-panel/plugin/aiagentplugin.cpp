/*
    SPDX-FileCopyrightText: 2026 KDE AI Agent Contributors
    SPDX-License-Identifier: GPL-2.0-or-later
*/

#include "aiagentplugin.h"

#include <KWindowSystem>
#include <KWindowEffects>
#include <LayerShellQt/window.h>
#include <PlasmaQuick/AppletQuickItem>

#include <QGuiApplication>
#include <QCursor>
#include <QScreen>
#include <QQuickWindow>
#include <QWindow>

AiAgentPanel::AiAgentPanel(QObject *parent, const KPluginMetaData &data, const QVariantList &args)
    : Plasma::Containment(parent, data, args)
{
    QQuickWindow::setDefaultAlphaBuffer(true);
}

AiAgentPanel::~AiAgentPanel() = default;

// -- Screen helpers --

QScreen *AiAgentPanel::screenForCursor() const
{
    const QPoint pos = QCursor::pos();
    for (auto *screen : QGuiApplication::screens()) {
        if (screen->geometry().contains(pos))
            return screen;
    }
    return nullptr;
}

QScreen *AiAgentPanel::screenForPanel() const
{
    int idx = screen();
    const auto screens = QGuiApplication::screens();
    return (idx >= 0 && idx < screens.size()) ? screens.at(idx) : nullptr;
}

// -- Wayland (LayerShellQt) --

void AiAgentPanel::configureWayland(QWindow *window)
{
    auto *layer = LayerShellQt::Window::get(window);
    layer->setLayer(LayerShellQt::Window::LayerTop);
    layer->setKeyboardInteractivity(LayerShellQt::Window::KeyboardInteractivityOnDemand);
    layer->setScope(QStringLiteral("ai-agent-panel"));
    // Anchor to left side — side panel
    layer->setAnchors(QFlags<LayerShellQt::Window::Anchor>(LayerShellQt::Window::AnchorLeft
                      | LayerShellQt::Window::AnchorTop
                      | LayerShellQt::Window::AnchorBottom));
    layer->setExclusiveZone(window->width());
}

void AiAgentPanel::updateScreenWayland(QWindow *window, QScreen *target, bool useActiveScreen)
{
    auto *layer = LayerShellQt::Window::get(window);

    if (layer->metaObject()->indexOfProperty("wantsToBeOnActiveScreen") >= 0) {
        if (useActiveScreen || !target) {
            layer->setProperty("wantsToBeOnActiveScreen", true);
        } else {
            layer->setProperty("wantsToBeOnActiveScreen", false);
            layer->setProperty("screen", QVariant::fromValue(target));
        }
    } else {
        if (target)
            window->setScreen(target);
        QT_WARNING_PUSH
        QT_WARNING_DISABLE_DEPRECATED
        layer->setScreenConfiguration(
            useActiveScreen ? LayerShellQt::Window::ScreenFromCompositor
                            : LayerShellQt::Window::ScreenFromQWindow);
        QT_WARNING_POP
    }
}

// -- Public API --

void AiAgentPanel::configureWindow(QWindow *window)
{
    if (!window)
        return;

    auto fmt = window->format();
    fmt.setAlphaBufferSize(8);
    window->setFormat(fmt);

    if (KWindowSystem::isPlatformWayland()) {
        configureWayland(window);
    }
}

void AiAgentPanel::updateWindowScreen(QWindow *window, bool useActiveScreen)
{
    if (!window || !KWindowSystem::isPlatformWayland())
        return;

    QScreen *target = useActiveScreen ? screenForCursor() : screenForPanel();
    updateScreenWayland(window, target, useActiveScreen);
}

void AiAgentPanel::setBlurBehind(QWindow *window, bool enable, int x, int y, int w, int h, int radius)
{
    if (!window)
        return;

    QRegion region;
    if (enable && w > 0 && h > 0) {
        const int d = radius * 2;
        QRegion rect(x, y, w, h);

        QRegion corners;
        corners += QRegion(x, y, radius, radius);
        corners += QRegion(x + w - radius, y, radius, radius);
        corners += QRegion(x, y + h - radius, radius, radius);
        corners += QRegion(x + w - radius, y + h - radius, radius, radius);
        rect -= corners;

        rect += QRegion(x, y, d, d, QRegion::Ellipse);
        rect += QRegion(x + w - d, y, d, d, QRegion::Ellipse);
        rect += QRegion(x, y + h - d, d, d, QRegion::Ellipse);
        rect += QRegion(x + w - d, y + h - d, d, d, QRegion::Ellipse);

        region = rect;
    }

    KWindowEffects::enableBlurBehind(window, enable, region);
}

void AiAgentPanel::setInputRect(QWindow *window, int x, int y, int w, int h)
{
    if (!window)
        return;

    if (w <= 0 || h <= 0) {
        window->setMask(QRegion());
        return;
    }
    window->setMask(QRegion(QRect(x, y, w, h)));
}
