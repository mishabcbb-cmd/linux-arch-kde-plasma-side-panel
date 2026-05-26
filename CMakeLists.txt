cmake_minimum_required(VERSION 3.28)
project(kde-ai-agent-native
    VERSION 0.3.0
    DESCRIPTION "KDE AI Agent — C++ native layer (pybind11)"
    LANGUAGES CXX C
)

# ── C++ Standard ──
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── Build type ──
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Release")
endif()

# ── Compiler flags ──
include(cmake/CompilerFlags.cmake)

# ── Find pybind11 ──
find_package(pybind11 REQUIRED)
message(STATUS "pybind11: ${pybind11_INCLUDE_DIRS}")

# ── Optional: llama.cpp from source ──
option(BUILD_LLAMA "Build llama.cpp from source for local inference" OFF)
if(BUILD_LLAMA)
    include(cmake/BuildLlama.cmake.in)
endif()

# ── Native RAG module ──
pybind11_add_module(rag_native
    src/rag_native.cpp
    src/embedding.cpp
    src/tokenizer.cpp
)

target_include_directories(rag_native PRIVATE src)
target_link_libraries(rag_native PRIVATE pybind11::module)

if(BUILD_LLAMA AND TARGET llama)
    target_compile_definitions(rag_native PRIVATE HAS_LLAMA=1)
    target_link_libraries(rag_native PRIVATE llama)
    target_include_directories(rag_native PRIVATE ${llama_SOURCE_DIR})
endif()

# ── Install ──
install(TARGETS rag_native
    DESTINATION ${CMAKE_INSTALL_PREFIX}/lib/python3.14/site-packages/agent
)

# ── Testing ──
enable_testing()
add_test(NAME test_rag_native
    COMMAND ${CMAKE_COMMAND} -E env
        PYTHONPATH=${CMAKE_BINARY_DIR}
        python3 -c "import rag_native; print('OK:', rag_native.__doc__)"
)
