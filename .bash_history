pacman -S Autogen
sudo pacman -S Autogen

sudo pacman -S --needed base-devel git
git clone https://arch
sudo pacman -S pacman-mirrorlist
sudo pacman -S --needed kitty
sudo pacman -S --needed starship
sudo pacman -S --needed fish
sudo pacman -S --needed nvidia-container-toolkit
sudo pacman -S --needed uv
sudo pacman -S --needed pm2
sudo pacman -S --needed libssl
sudo pacman -S --needed rust
sudo pacman -S --needed go wget
sudo pacman -S --needed openssl
sudo pacman -S --needed cuda curl cudnn
sudo pacman -S --needed clang btrfs-progs python-pip python git fish ninja
sudo pacman -S --needed pkg-config lib32-nvidia-utils
sudo pacman -S --needed lib32-opencl-nvidia
sudo pacman -S --needed opencl-headers
sudo pacman -S --needed opencl-clhpp
reboot
sudo pacman -S --needed pkg-config lib32-nvidia-utils lib32-opencl-utils
sudo pacman -S --needed pkg-config lib32-nvidia-utils lib32-opencl
sudo pacman -S --needed lib32-opencl-nvidia
sudo pacman -S --needed plasma
sudo pacman -S --needed kde-plasma-applications
sudo pacman -S --needed kde-applications
sudo pacman -S --needed kde-applications
sudo pacman -S --needed plasma-login-manager
systemctl enable plasmalogin.service
reboot
sudo pacman -S --needed yay
sudo pacman -Syu
sudo pacman -S --needed base-devel git
sudo pacman -S --needed base-devel git
cd yay
mkdir home/neo/yay
sudo mkdir home/neo/yay
sudo mkdir home/neo/
cd ~
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si
cd ~
ls -d yay
yay -syu
yay -S -needed vscodium-bin docker-desktop steam discord 
yay -S --needed vscodium-bin docker-desktop steam discord 
# If using an AUR helper like yay:
yay -S timeshift grub-btrfs inotify-tools
sudo timeshift-gtk
sudo systemctl edit --full grub-btrfsd.service
sudo systemctl enable --now grub-btrfsd.service
yay -S lean-ctx-bin
lean-ctx --version
lean-ctx setup
lean-ctx init --agent roo --mode mcp
lean-ctx gain
exec fish
