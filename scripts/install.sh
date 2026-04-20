#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }

check_platform() {
    case "$(uname -s)" in
        Linux)  info "Detected Linux" ;;
        Darwin) info "Detected macOS" ;;
        *)      error "Unsupported platform: $(uname -s)"; exit 1 ;;
    esac
}

ensure_uv() {
    if command -v uv &>/dev/null; then
        info "uv is already installed: $(uv --version)"
        return
    fi

    info "Installing uv..."
    if ! command -v curl &>/dev/null; then
        error "curl is required to install uv"
        exit 1
    fi

    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    success "uv installed"
}

install_or_update_wingman() {
    if command -v wingman &>/dev/null; then
        info "Updating wingman-cli..."
        uv tool upgrade wingman-cli
        success "wingman-cli updated"
    else
        info "Installing wingman-cli..."
        uv tool install wingman-cli
        success "wingman-cli installed"
    fi
}

main() {
    cat <<'ART'

                                                ..
                                                ..
                                               ...
                                              ....
                                             ....
                                            .....
                                           .....
                                         ......
                                      ........
                                    ........
                                 .........
                             ...........       ...
                         ............         ....
                     .............           ....
                 ..............            .....
             ..............              ......
         ..............                .......
      ............                   .......
    .........                     ........
  ........                     .........
 ......                   ...........
......               ............
.....                                      ..
....                                    ....
...                                    ....
..                                 .......
.                            ..........
.               ....................
.            ..................

  Wingman - AI coding assistant for the terminal

ART
    check_platform
    ensure_uv
    install_or_update_wingman

    if command -v wingman &>/dev/null; then
        echo
        success "Ready! Run:"
        echo "  wingman"
        echo
    else
        warning "'wingman' not found in PATH"
        warning "Add ~/.local/bin to your PATH:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        exit 1
    fi
}

main
