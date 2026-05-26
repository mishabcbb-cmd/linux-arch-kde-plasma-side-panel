# Dockerfile — KDE AI Agent (headless mode)
#
# Build: docker build -t kde-ai-agent .
# Run:   docker run -v ~/.config/kde-ai-agent:/root/.config/kde-ai-agent kde-ai-agent
#
# Note: For full KDE Plasma integration, run natively.
# This image is for headless/API mode.

FROM archlinux:latest AS builder

# System deps
RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm \
        python python-pip python-dbus \
        cmake gcc pybind11 \
        ripgrep tree-sitter \
        git \
    && pacman -Scc --noconfirm

WORKDIR /app

# Copy source
COPY agent/ agent/
COPY tests/ tests/
COPY CMakeLists.txt cmake/ src/ ./

# Install Python deps
RUN pip install --break-system-packages -r agent/requirements.txt && \
    pip install --break-system-packages pytest

# Build native layer
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j$(nproc) || echo "Native build optional"

# Runtime stage
FROM archlinux:latest

RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm \
        python python-pip python-dbus \
        ripgrep tree-sitter \
        espeak-ng \
    && pacman -Scc --noconfirm

WORKDIR /app

COPY --from=builder /app/agent/ agent/
COPY --from=builder /app/build/ build/

RUN pip install --break-system-packages -r agent/requirements.txt

# Expose MCP SSE port
EXPOSE 8765

# Default: run as MCP SSE server
CMD ["python", "-m", "agent.main", "--mcp-sse"]
