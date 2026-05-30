/*
    SPDX-FileCopyrightText: 2026 KDE AI Agent Contributors
    SPDX-License-Identifier: GPL-2.0-or-later

    C++ plugin for AI Agent Panel — a Plasma::Containment panel with LayerShell.
    Provides configureWindow() for Wayland LayerShell setup.
*/

#ifndef AIAGENTPLUGIN_H
#define AIAGENTPLUGIN_H

#include <Plasma/Containment>
#include <QWindow>
#include <QScreen>

class AiAgentPanel : public Plasma::Containment
{
    Q_OBJECT

public:
    explicit AiAgentPanel(QObject *parent, const KPluginMetaData &data, const QVariantList &args = {});
    ~AiAgentPanel() override;

    /// Configure the panel's QWindow for Wayland LayerShell.
    Q_INVOKABLE void configureWindow(QWindow *window);

    /// Update which screen the panel is on (Wayland only).
    Q_INVOKABLE void updateWindowScreen(QWindow *window, bool useActiveScreen);

    /// Set blur behind a region of the panel.
    Q_INVOKABLE void setBlurBehind(QWindow *window, bool enable, int x, int y, int w, int h, int radius = 0);

    /// Set input mask so events pass through outside the given rect.
    Q_INVOKABLE void setInputRect(QWindow *window, int x, int y, int w, int h);

private:
    void configureWayland(QWindow *window);
    void updateScreenWayland(QWindow *window, QScreen *target, bool useActiveScreen);

    QScreen *screenForCursor() const;
    QScreen *screenForPanel() const;
};

#endif // AIAGENTPLUGIN_H
