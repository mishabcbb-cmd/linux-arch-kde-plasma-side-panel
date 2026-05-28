#!/bin/bash
# Остановить всех A2A агентов

if [ -f /tmp/a2a-agents.pids ]; then
    PIDS=$(cat /tmp/a2a-agents.pids)
    echo "Stopping agents: $PIDS"
    kill $PIDS 2>/dev/null || true
    rm /tmp/a2a-agents.pids
    echo "All agents stopped."
else
    echo "No agents PID file found. Stopping by port..."
    for port in 8091 8092 8093; do
        pid=$(lsof -ti :$port 2>/dev/null)
        if [ -n "$pid" ]; then
            kill $pid 2>/dev/null
            echo "  Stopped agent on :$port (PID: $pid)"
        fi
    done
fi

# Остановить Hub
hub_pid=$(lsof -ti :9000 2>/dev/null)
if [ -n "$hub_pid" ]; then
    kill $hub_pid 2>/dev/null
    echo "  Stopped Hub (PID: $hub_pid)"
fi

echo "Done."
