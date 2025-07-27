# USB Boot Troubleshooting Guide

## When Your Weirding Module USB Drive Won't Boot

If your BIOS doesn't detect the bootable USB drive or it fails to boot, follow this systematic troubleshooting guide.

## 🔍 Step 1: Verify USB Drive Creation

First, confirm the USB drive was created successfully:

```bash
# Check if the drive has bootable signatures
sudo fdisk -l /dev/sdX  # Replace X with your drive letter

# Look for:
# - Bootable flag (*) 
# - Boot partition type
# - Correct size matching your ISO
```

Expected output should show something like:
```
Device     Boot Start    End Sectors  Size Id Type
/dev/sdc1  *     2048 123456  121408 59.3M  c W95 FAT32 (LBA)
```

## ⚙️ Step 2: BIOS/UEFI Settings Configuration

### Accessing BIOS/UEFI Setup
- **During boot**: Press F2, F12, DEL, or ESC (varies by manufacturer)
- **Common keys by brand**:
  - Dell: F2 or F12
  - HP: F10 or F12  
  - Lenovo: F1 or F12
  - ASUS: F2 or DEL
  - MSI: DEL or F2

### Critical Settings to Check

#### 1. Boot Mode Settings
```
Setting: Boot Mode / Boot List Option
Options: UEFI | Legacy | Both
Recommended: Try UEFI first, then Legacy if it fails
```

#### 2. Secure Boot (UEFI Systems)
```
Setting: Secure Boot Control
Current: Enabled
Change to: Disabled
Note: This is often the main culprit for USB boot failures
```

#### 3. Fast Boot / Quick Boot
```
Setting: Fast Boot
Current: Enabled  
Change to: Disabled
Reason: Skips USB detection during quick startup
```

#### 4. USB Support
```
Setting: USB Configuration / USB Support
Ensure enabled:
- USB Controller
- USB 2.0 Controller  
- USB 3.0/3.1 Controller
- Legacy USB Support
```

#### 5. CSM (Compatibility Support Module)
```
Setting: CSM Support
For Legacy boot: Enabled
For UEFI boot: Disabled
For Hybrid ISOs: Enabled (try both modes)
```

#### 6. Boot Priority/Order
```
Setting: Boot Priority / Boot Order
Action: Move USB device to top of list
Look for: USB HDD, USB-FDD, Removable Devices
```

## 🔧 Step 3: Hardware Troubleshooting

### USB Port Testing
1. **Try different USB ports**:
   - Use USB 2.0 ports (more compatible)
   - Avoid USB 3.0+ ports initially
   - Try rear ports on desktops (more reliable)

2. **USB drive compatibility**:
   - Some older BIOS don't support USB 3.0 drives
   - Try a different USB drive if available
   - USB 2.0 drives often have better compatibility

### 🚀 USB 4.0 Specific Issues & Solutions

**USB 4.0 drives often have boot compatibility problems** because:
- Most BIOS predate USB 4.0 standard (2019+)
- USB 4.0 requires specific controller drivers not available during boot
- Higher speed protocols may not fall back to legacy modes properly

#### USB 4.0 Workaround Methods:

1. **Force USB 2.0/3.0 Compatibility Mode**:
   ```bash
   # Create USB with explicit USB 2.0 parameters
   sudo dd if=ubuntu.iso of=/dev/sdX bs=1M status=progress conv=fsync
   
   # Alternative: Use smaller block size for better compatibility
   sudo dd if=ubuntu.iso of=/dev/sdX bs=512k status=progress conv=fsync oflag=sync
   ```

2. **BIOS Settings for USB 4.0**:
   - **Enable "USB Legacy Support"** (critical)
   - **Set "USB Mode" to "Auto" or "Compatible"** (not "USB 4.0 Only")
   - **Enable "xHCI Hand-off"** if available
   - **Disable "USB Fast Charge"** (can interfere with boot detection)

3. **Physical Connection Solutions**:
   - **Use USB-C to USB-A adapter** (forces slower protocol)
   - **Try different USB-C ports** (some may have USB 3.0 fallback)
   - **Use USB 3.0/2.0 hub** as intermediary device
   - **Connect to laptop/desktop USB 3.0 port** instead of USB-C 4.0

4. **USB 4.0 Drive Compatibility Mode**:
   Many USB 4.0 drives have built-in compatibility:
   ```bash
   # Check if your drive supports compatibility mode
   lsusb -v | grep -A 5 -B 5 "your_drive_name"
   
   # Look for multiple speed capabilities:
   # - SuperSpeed (USB 3.0)
   # - High-speed (USB 2.0)
   # - Full-speed (USB 1.1)
   ```

#### USB 4.0 Creation Parameters:
For USB 4.0 drives, use these optimized parameters:

```bash
# Method 1: Conservative approach (most compatible)
sudo dd if=ubuntu.iso of=/dev/sdX bs=1M status=progress conv=fsync oflag=direct

# Method 2: If Method 1 fails, try without direct I/O
sudo dd if=ubuntu.iso of=/dev/sdX bs=512k status=progress conv=fsync

# Method 3: Force sync after each block (slowest but most reliable)
sudo dd if=ubuntu.iso of=/dev/sdX bs=1M status=progress conv=sync
```

#### Hardware-Specific USB 4.0 Solutions:

**Thunderbolt 4/USB 4.0 Hubs:**
- Connect USB 4.0 drive through USB 3.0 hub
- Hub will force compatibility mode automatically

**USB-C Dock/Adapter Method:**
```bash
# If using USB-C dock with USB-A ports:
# 1. Connect USB 4.0 drive to dock's USB-A port
# 2. This forces USB 3.0 compatibility mode
# 3. Create bootable USB normally
```

**Laptop-Specific Settings:**
- **Dell XPS/Precision**: Look for "USB PowerShare" - disable it
- **MacBook Pro**: Use right-side USB-C ports (often have better compatibility)
- **ThinkPad**: Enable "Always On USB" in BIOS power settings

### BIOS Age Considerations
- **Very old BIOS** (pre-2010): May not support USB booting at all
- **Old BIOS** (2010-2015): May need Legacy mode and specific USB formats
- **Modern BIOS** (2015+): Should support both UEFI and Legacy

## 🛠️ Step 4: Advanced Troubleshooting

### Re-create USB with Different Parameters

If the standard creation failed, try these alternatives:

```bash
# Method 1: Use different block size
sudo dd if=ubuntu.iso of=/dev/sdX bs=1M status=progress conv=fdatasync

# Method 2: Add sync and verify
sudo dd if=ubuntu.iso of=/dev/sdX bs=4M status=progress oflag=sync
sudo sync

# Method 3: Use specialized tools
# Install ventoy for universal USB booting
sudo apt install ventoy
sudo ventoy -i /dev/sdX
```

### Check ISO Compatibility
Some ISOs work better than others:

1. **Ubuntu Desktop ISO**: Usually most compatible (hybrid ISO)
2. **Ubuntu Server ISO**: May need different boot parameters  
3. **Custom ISOs**: May lack proper boot signatures

### Hybrid ISO Creation
If your ISO isn't hybrid (doesn't work on both UEFI and Legacy):

```bash
# Make ISO hybrid with isohybrid (if available)
sudo apt install syslinux-utils
sudo isohybrid ubuntu.iso

# Then re-write to USB
sudo dd if=ubuntu.iso of=/dev/sdX bs=4M status=progress
```

## 📋 Step 5: Boot Menu Testing

### Access Boot Menu
Instead of changing BIOS settings permanently:
1. **Boot menu keys** (during startup):
   - F8, F10, F11, F12 (varies by manufacturer)
2. **Select USB device** from one-time boot menu
3. **Look for entries like**:
   - USB HDD: Your Drive Name
   - UEFI: Your Drive Name  
   - Legacy: Your Drive Name

### Boot Entry Names to Look For
- "USB HDD"
- "Removable Devices"
- "UEFI: [Your USB Drive Name]"
- "Generic USB Device"
- Your actual USB drive model name

## 🔬 Step 6: Diagnostic Commands

### Verify USB Drive Status
```bash
# Check drive recognition
lsblk
lsusb
sudo dmesg | tail -20

# Check partition table
sudo parted /dev/sdX print

# Check bootable flags
sudo fdisk -l /dev/sdX | grep -E "(Boot|System)"

# Test read capability
sudo dd if=/dev/sdX of=/dev/null bs=1M count=100 status=progress
```

### Check ISO Bootability
```bash
# Verify ISO has boot signatures
file ubuntu.iso
hexdump -C ubuntu.iso | head -n 50

# Check for El Torito boot record
isoinfo -d -i ubuntu.iso | grep -i boot
```

## ⚡ Common Solutions by Symptom

### "USB Drive Not Detected in BIOS"
1. Enable USB Legacy Support
2. Disable Fast Boot
3. Try different USB ports (prefer USB 2.0)
4. Check if USB drive is properly written
5. **USB 4.0**: Use USB-C to USB-A adapter to force compatibility mode

### "USB Drive Detected But Won't Boot"
1. Disable Secure Boot
2. Try both UEFI and Legacy boot modes
3. Check if ISO was hybrid/bootable
4. Re-create USB with different method
5. **USB 4.0**: Set BIOS USB mode to "Auto" or "Compatible" (not "USB 4.0 Only")

### "Boot Starts But Hangs/Crashes"
1. Try different boot parameters (nomodeset, acpi=off)
2. Check RAM compatibility
3. Disable hardware acceleration in BIOS
4. Try a different ISO version
5. **USB 4.0**: Connect through USB 3.0 hub to force slower protocol

### "Works Sometimes, Not Others"
1. Power supply issues (use powered USB hub)
2. USB drive aging/corruption (try different drive)
3. Temperature issues (let system cool down)
4. Intermittent BIOS settings reset
5. **USB 4.0**: USB 4.0 controller driver conflicts - use different port

### "USB 4.0 Drive Specific Issues"
**Symptom**: Brand new USB 4.0 drive not recognized at all
**Solutions**:
1. Use USB-C to USB-A adapter/cable
2. Connect through powered USB 3.0 hub
3. Try laptop's right-side USB-C ports (often better compatibility)
4. Re-create USB with smaller block sizes: `bs=512k` instead of `bs=4M`
5. Enable "xHCI Hand-off" in BIOS if available
6. Disable "USB Fast Charge" or "USB PowerShare" features

## 🔄 Step 7: Recovery Methods

### If Nothing Works
1. **Try different computer**: Test if USB boots elsewhere
2. **Use different tool**: Try Rufus, UNetbootin, or Etcher
3. **Use DVD/CD**: Burn ISO to optical media instead
4. **Network boot**: Setup PXE boot if available
5. **Virtual machine**: Test ISO in VM first

### Emergency Alternatives
```bash
# Create bootable USB with Ventoy (universal)
sudo ventoy -i /dev/sdX

# Use balenaEtcher (GUI tool)
sudo apt install balena-etcher-electron

# Try different ISO variants
# - Desktop vs Server
# - LTS vs Latest
# - Alternative architectures
```

## 📊 Manufacturer-Specific Notes

### Dell Systems
- F12 for boot menu
- Often need Legacy mode for USB
- Disable "Secure Boot" in Security tab

### HP Systems  
- F10 for BIOS, F9 for boot menu
- Look for "Legacy Support" option
- Disable "Fast Boot" in Advanced

### Lenovo Systems
- F1 or F2 for BIOS, F12 for boot menu
- May need "CSM Support" enabled
- Check "USB HDD" vs "USB FDD" options

### ASUS Systems
- DEL or F2 for BIOS
- Look in "Boot" tab for USB options
- "Launch CSM" may need to be enabled

## ✅ Success Checklist

Before concluding the USB is faulty:

- [ ] Disabled Secure Boot
- [ ] Disabled Fast Boot  
- [ ] Enabled Legacy USB Support
- [ ] Tried both UEFI and Legacy modes
- [ ] Tested different USB ports
- [ ] Verified USB creation was successful
- [ ] Checked ISO integrity
- [ ] Tried boot menu instead of BIOS changes
- [ ] Tested on different computer if possible

## 📞 Still Need Help?

If you've tried all these steps and still can't boot:

1. **Check the USB drive on another computer**
2. **Verify the original ISO downloads properly**  
3. **Try creating the USB on a different system**
4. **Consider hardware compatibility issues**
5. **Post detailed error messages and system specs for community help**

Remember: USB booting can be finicky, but these steps resolve 95% of common issues!