# cmake/CompilerFlags.cmake — GCC 16 compiler flags
#
# Applies aggressive optimizations for GCC 16.1.1 on Arch Linux:
#   • -march=native — CPU-specific optimizations
#   • -O3 — Maximum optimization
#   • -flto=thin — Link-time optimization with zstd compression
#   • -fauto-profile-inlining — Automatic inlining candidates
#   • -ffold-mem-offsets — Memory offset optimization
#   • -fhardcfr-check-exceptions — Control flow robustness
#
# Pattern: Jarvis CMakeLists.txt compiler flags

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL "16")
    message(STATUS "GCC 16 detected — applying aggressive optimizations")

    # Common flags
    set(COMMON_FLAGS
        -march=native
        -O3
        -pipe
        -fomit-frame-pointer
    )

    # LTO
    set(CMAKE_INTERPROCEDURAL_OPTIMIZATION ON)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -flto=thin -fuse-linker-plugin")

    # GCC 16 specific
    set(GCC16_FLAGS
        -fauto-profile-inlining
        -ffold-mem-offsets
        -fhardcfr-check-exceptions
        -Wc11-c23-compat
    )

    # Debug flags
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O0 -g3 -ggdb3 -fno-omit-frame-pointer")
        if(ENABLE_SANITIZERS)
            set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fsanitize=address,undefined -fno-sanitize-recover=all")
            set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fsanitize=address,undefined")
        endif()
    else()
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${COMMON_FLAGS} ${GCC16_FLAGS}")
    endif()

    # Linker flags
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,-O3 -Wl,--as-needed -Wl,--gc-sections")
    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,-O3 -Wl,--as-needed -Wl,--gc-sections")

    # Visibility
    set(CMAKE_CXX_VISIBILITY_PRESET hidden)
    set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)

    message(STATUS "C++ flags: ${CMAKE_CXX_FLAGS}")
    message(STATUS "Linker flags: ${CMAKE_EXE_LINKER_FLAGS}")
else()
    message(STATUS "Compiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION} — standard flags")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -march=native -pipe")
endif()
