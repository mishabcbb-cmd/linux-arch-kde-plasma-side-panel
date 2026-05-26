/*
 * contents/config/config.qml — Settings page for the AI Agent Panel.
 *
 * Configuration categories:
 *   1. API — Provider selection, API key, model selector
 *   2. Working Directory — Path picker for project root
 *   3. Advanced — OpenObserve endpoint, token limits
 *
 * Pattern: JARVIS config.qml (ConfigModel + ConfigCategory)
 */

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.configuration 2.0
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents

ConfigModel {
    ConfigCategory {
        name: i18n("API Configuration")
        icon: "network-connect"
        source: "ConfigApi.qml"
    }
    ConfigCategory {
        name: i18n("Working Directory")
        icon: "folder"
        source: "ConfigDirectory.qml"
    }
    ConfigCategory {
        name: i18n("Advanced")
        icon: "configure"
        source: "ConfigAdvanced.qml"
    }
}
