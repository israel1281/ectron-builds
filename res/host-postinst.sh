if [ "$1" = configure ]; then
    echo "Configuring @BINARY@ for unattended host access."
    systemctl enable --now @BINARY@
    configured=false
    for attempt in $(seq 1 20); do
        if /usr/bin/@BINARY@ --setup-host; then
            configured=true
            break
        fi
        sleep 2
    done
    if [ "$configured" != true ]; then
        echo "Host setup failed. Check the @BINARY@ service, then run sudo dpkg --configure @BINARY@." >&2
        exit 1
    fi
fi
