#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}"
echo "=========================================="
echo "   GPG Key Generation for APT Repository"
echo "=========================================="
echo -e "${NC}"

# Generate GPG key
echo -e "${BLUE}Generating GPG key...${NC}"
gpg --batch --gen-key <<EOF
Key-Type: RSA
Key-Length: 4096
Name-Real: Uptime Monitor
Name-Email: yaroslav.andreichuk@gmail.com
Expire-Date: 0
%no-protection
%commit
EOF

# Export the public key
echo -e "${BLUE}Exporting public key...${NC}"
gpg --armor --export yaroslav.andreichuk@gmail.com > KEY_PUBLIC.gpg

# Export the private key (for signing packages)
echo -e "${BLUE}Exporting private key...${NC}"
gpg --armor --export-secret-key yaroslav.andreichuk@gmail.com > KEY_PRIVATE.gpg

# Dearmor the public key for APT
echo -e "${BLUE}Creating dearmor version for APT...${NC}"
gpg --dearmor --export-options export-local-sigs --export yaroslav.andreichuk@gmail.com > KEY_DEARMOR.gpg

echo -e "${GREEN}"
echo "=========================================="
echo "   GPG Keys Generated Successfully!"
echo "=========================================="
echo -e "${NC}"
echo ""
echo "Files created:"
echo "  - KEY_PUBLIC.gpg (public key)"
echo "  - KEY_PRIVATE.gpg (private key - keep this safe!)"
echo "  - KEY_DEARMOR.gpg (dearmor version for APT)"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC}"
echo "  1. Upload KEY_PUBLIC.gpg and KEY_DEARMOR.gpg to your GitHub repository"
echo "  2. Update the APT repository configuration to use the correct URL"
echo "  3. Keep KEY_PRIVATE.gpg secure and don't share it"
echo ""