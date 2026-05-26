/*
 * contents/config/ConfigDirectory.qml — Working directory configuration.
 *
 * All fields bound to Plasmoid.configuration for persistence.
 */

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.plasmoid

Item {
    id: configDirRoot
    width: parent ? parent.width : 0
    height: parent ? parent.height : 0

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: 0

            Kirigami.FormLayout {
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("Working Directory")
                }

                Label {
                    text: i18n("The working directory is where the agent operates. All file read/write, search, and test operations are scoped to this directory.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Directory:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.TextField {
                        id: workingDirField
                        text: plasmoid.configuration.workingDir || "~"
                        placeholderText: "~/projects/my-project"
                        Layout.fillWidth: true
                        onTextChanged: plasmoid.configuration.workingDir = text
                    }

                    PlasmaComponents.Button {
                        icon.name: "folder-open"
                        text: i18n("Browse...")
                        onClicked: dirDialog.open()
                    }
                }

                Label {
                    text: i18n("Use ~ for your home directory. The agent creates git commits in this directory.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }

            Kirigami.FormLayout {
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("Git Settings")
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Auto-commit:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.Switch {
                        id: autoCommitSwitch
                        checked: plasmoid.configuration.autoCommit !== false
                        onCheckedChanged: plasmoid.configuration.autoCommit = checked
                    }

                    Label {
                        text: autoCommitSwitch.checked ? i18n("Enabled") : i18n("Disabled")
                        color: autoCommitSwitch.checked ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor
                    }
                }

                Label {
                    text: i18n("When enabled, the agent automatically creates git commits after each file write.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }

            Item { Layout.fillHeight: true }
        }
    }

    // Directory picker dialog
    FileDialog {
        id: dirDialog
        title: i18n("Select Working Directory")
        selectFolder: true
        onAccepted: {
            var path = dirDialog.fileUrl.toString()
            if (path.startsWith("file://")) {
                path = path.substring(7)
            }
            workingDirField.text = path
            plasmoid.configuration.workingDir = path
        }
    }
}
