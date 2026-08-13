# CalibrateSDR
what is my SDR frequency?


## Troubleshooting

If running the program throws error- ```AttributeError: python: undefined symbol: rtlsdr_get_device_count```, try this:
 
Refer to this [issue](https://github.com/roger-/pyrtlsdr/issues/7#issuecomment-47391543). If it still persists, build [librtlsdr](https://github.com/librtlsdr/librtlsdr) from it source and make sure it's path is defined correctly. 

* Arch-based OS: use AUR source [rtl-sdr-librtlsdr](https://aur.archlinux.org/packages/rtl-sdr-librtlsdr-git/)
* Ubuntu/ Debiam based OS: Run ```sudo apt update && sudo apt install librtlsdr-dev```
* On Windows, it gets automatically installed while using ```pip install pyrtlsdr```

Note: After installing, make sure PATH has been define accordingly, for example: ```export LD_LIBRARY_PATH="/usr/local/lib"```

## Compatibility with some R828D-based RTL-SDR devices

Problems have been observed with some R828D-based RTL-SDR dongles (e.g. certain no bias-T
variants) when using librtlsdr's asynchronous USB transfer mode, which queues 32 concurrent
transfers. These devices return `LIBUSB_ERROR_BUSY` errors, causing I2C communication failures
and crashes. The root cause is likely an interaction between the specific RTL-SDR PCB revision,
the USB host controller, and the driver stack, rather than age alone.

To support these devices, this fork uses synchronous USB reads (`rtlsdr_read_sync` via
`pyrtlsdr.read_samples()`) instead of the original asynchronous path. This works correctly
across all tested hardware but loads all samples into memory before writing to disk, rather
than streaming. At the default 2.048 MHz sample rate, a 10-second scan uses ~328 MB of RAM.
This is well within normal limits — DAB PPM calibration only requires a few seconds of data.

Additionally, `get_fft()` now casts uint8 data to float before applying the ADC offset to
prevent an overflow error, and channel scanning includes per-channel error handling so one
failed channel does not abort the entire scan.
