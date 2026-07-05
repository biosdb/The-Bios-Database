ROM entries were sourced from two collections:

- [macmade/Macintosh-ROMs](https://github.com/macmade/Macintosh-ROMs) — 68k ROM files covering the Classic, LC, Performa, Centris, and Quadra lines.
- [Macintosh Repository — All Macintosh ROMs (68k & PPC)](https://www.macintoshrepository.org/7038-all-macintosh-roms-68k-ppc-) — a comprehensive archive including 64KB, 128KB, 256KB, and 512KB ROMs with Apple ROM IDs in the filenames.

The `version` field on each entry records the Apple ROM ID (the internal checksum identifier embedded in the ROM, as reported by emulators and ROM tools). This is distinct from the `crc32` field, which is the standard CRC32 of the file binary.
