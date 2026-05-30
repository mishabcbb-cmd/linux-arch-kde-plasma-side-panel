# CMakeLists.txt for AI Agent Panel C++ plugin
# Pattern: AppGrid's CMakeLists.txt

cmake_minimum_required(VERSION 3.20)
project(aiagentpanelplugin VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(ECM 6.0 REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
include(KDEInstallDirs)

find_package(Qt6 REQUIRED COMPONENTS Core Quick Gui)
find_package(KF6 REQUIRED COMPONENTS
    Config
    CoreAddons
    WindowSystem
)
find_package(LayerShellQt REQUIRED)
find_package(Plasma REQUIRED)
find_package(PlasmaQuick REQUIRED)

configure_file(${CMAKE_CURRENT_SOURCE_DIR}/metadata.json.in
    ${CMAKE_CURRENT_BINARY_DIR}/metadata.json @ONLY)

add_library(aiagentpanelplugin SHARED
    aiagentplugin.cpp
    aiagentplugin_register.cpp
)

set_target_properties(aiagentpanelplugin PROPERTIES PREFIX "")

target_link_libraries(aiagentpanelplugin PRIVATE
    Qt6::Core
    Qt6::Quick
    Qt6::Gui
    KF6::ConfigCore
    KF6::CoreAddons
    KF6::WindowSystem
    LayerShellQt::Interface
    Plasma::Plasma
    Plasma::PlasmaQuick
)

install(TARGETS aiagentpanelplugin
    DESTINATION ${KDE_INSTALL_PLUGINDIR}/plasma/applets
)

# Install metadata.json to the plasmoid package directory
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/metadata.json
    DESTINATION ${KDE_INSTALL_DATADIR}/plasma/plasmoids/org.kde.plasma.ai-agent-panel
)
