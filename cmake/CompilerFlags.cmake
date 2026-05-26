# cmake/CompilerFlags.cmake — GCC compiler flags
#
# Uses add_compile_options() to avoid CMake list semicolon issues.
# Applies aggressive optimizations for GCC 15/16 on Arch Linux.
#
# Pattern: Jarvis CMakeLists.txt compiler flags

# Detect GCC version
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU")
    message(STATUS "GCC ${CMAKE_CXX_COMPILER_VERSION} detected")
    if(CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL "16")
        set(HAS_GCC16 ON)
        message(STATUS "GCC 16 features enabled")
    else()
        set(HAS_GCC16 OFF)
    endif()
else()
    message(STATUS "Compiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
    set(HAS_GCC16 OFF)
endif()

# Common flags for all GCC versions
add_compile_options(
    -march=native
    -O3
    -pipe
    -fomit-frame-pointer
)

# LTO (GCC uses -flto=auto, not -flto=thin which is Clang-only)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION ON)
add_compile_options(-flto=auto -fuse-linker-plugin)

# GCC 16 specific
if(HAS_GCC16)
    add_compile_options(
        -fauto-profile-inlining
        -ffold-mem-offsets
        -fhardcfr-check-exceptions
    )
    # -Wc11-c23-compat is C/ObjC only, not valid for C++
endif()

# Debug flags
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    add_compile_options(-O0 -g3 -ggdb3 -fno-omit-frame-pointer)
    if(ENABLE_SANITIZERS)
        add_compile_options(-fsanitize=address,undefined -fno-sanitize-recover=all)
        add_link_options(-fsanitize=address,undefined)
    endif()
endif()

# Linker flags
add_link_options(-Wl,-O3 -Wl,--as-needed -Wl,--gc-sections)

# Visibility
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)

message(STATUS "Compiler flags configured")
