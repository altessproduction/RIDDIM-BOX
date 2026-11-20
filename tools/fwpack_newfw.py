#!/usr/bin/env python3
"""
fwpack_newfw.py - Repacker pour les packages .fwsc JieLi "new firmware"
(inverse de fwunpack_newfw.py de kagaimiq/jl-misctools).

Cible : M-VAVE FM-1 (JieLi AC791N/WL82) - RIDDIM ROOTS et derives.

Structure d'un .fwsc :
  [20 blocs de 0x30 : en-tete UFW, 0x2F octets utiles + 1 octet "junk" chacun]
  [padding]
  [flash.bin : image flash partielle (0x0000-0x71000), telle que stockee]
  [ota.bin + divers]

Conventions CRC verifiees empiriquement sur RIDDIM ROOTS v0.3.0 :
  - UFW hdrcrc  = CRC16 sur les octets DECHIFFRES [2:0x40] de l'en-tete
  - UFW listcrc = CRC16 sur les octets CHIFFRES [0x40:headersize]
  - UFW edcrc (flash.bin/ota.bin) = CRC16 sur les donnees telles que stockees
  - JLFS (entree 32 o) : hcrc = CRC16 sur les 30 o d'en-tete (apres champ hcrc),
    edcrc = CRC16 sur les donnees FINALES (debrouillees pour uboot)
  - zone app : chiffrement sfc par blocs de 32 o, cle de bloc = chipkey ^ ((off-base)>>2)

Seuls les patches de TAILLE IDENTIQUE sont supportes (aucun deplacement).
"""
import struct
import sys
import argparse
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for cand in [_HERE, _HERE / 'jl-misctools' / 'firmware', _HERE / 'firmware']:
    if (cand / 'jltech' / 'crc.py').exists():
        sys.path.insert(0, str(cand))
        break
else:
    raise RuntimeError("modules jltech introuvables (jl-misctools requis)")

from jltech.crc import jl_crc16                                    # noqa: E402
from jltech.cipher import jl_enc_cipher, jl_sfc_cipher             # noqa: E402

###############################################################################

NBLOCKS    = 20
BLOCK      = 0x30
KEEP       = 0x2F
HEADERKEY  = 0xFFFF
APP_BASE   = 0x4000          # debut zone chiffree chipkey dans flash.bin
APP_END    = 0x71000         # fin de flash.bin
ISD_OFF    = 0x3938          # isd_config.ini dans flash.bin
ISD_SIZE   = 755


def descramble_bankcb(data: bytearray, base: int, key: int):
    """Debrouillage bankcb de l'uboot (symetrique)."""
    bankcount = 1
    index = 0
    while index < bankcount:
        hdroff = base + index * 16
        jl_enc_cipher(data, hdroff, 16, key)
        hdr, hcrc = struct.unpack_from('<14sH', data, hdroff)
        if jl_crc16(hdr) != hcrc:
            raise ValueError(f'Bank {index}: CRC en-tete invalide')
        bankid, banksize, _load, bankoff, _crc = struct.unpack('<HHIIH', hdr)
        if index == 0:
            bankcount = bankid
        jl_enc_cipher(data, base + bankoff, banksize, key)
        index += 1


class Fwsc:
    """Package .fwsc charge. flash.bin reste tel que stocke (chiffre)."""

    def __init__(self, raw: bytes):
        self.raw = bytes(raw)
        if len(raw) <= NBLOCKS * BLOCK:
            raise ValueError('fichier trop court')

        # reconstruction de l'en-tete depuis les 20 blocs
        self.hdr_crypt = bytearray()   # octets tels qu'aux positions utiles (chiffres)
        self.junk = bytearray()
        for i in range(NBLOCKS):
            blk = raw[i*BLOCK:(i+1)*BLOCK]
            self.hdr_crypt += blk[:KEEP]
            self.junk.append(blk[KEEP])

        # lecture de numents pour connaitre headersize
        tmp = bytearray(self.hdr_crypt[:0x40])
        jl_enc_cipher(tmp, 0, 0x40, HEADERKEY)
        _hcrc, _lcrc, imgsize, numents, _w3, _w4, chip = \
            struct.unpack_from('<HHIHHI48s', tmp, 0)
        self.imgsize, self.numents = imgsize, numents
        self.chipname = chip.split(b'\0')[0].decode('ascii', 'replace')
        self.headersize = 0x40 + numents * 0x50

        # version en clair des chunks signifiants [0:headersize]
        self.hdr_plain = bytearray(self.hdr_crypt[:self.headersize])
        jl_enc_cipher(self.hdr_plain, 0, 0x40, HEADERKEY)
        for off in range(0x40, self.headersize, 0x50):
            jl_enc_cipher(self.hdr_plain, off, 0x50, HEADERKEY)

        self.offskew = NBLOCKS * BLOCK - len(self.hdr_crypt)   # 20 ici

        # entrees UFW (en clair)
        self.entries = []
        for off in range(0x40, self.headersize, 0x50):
            etype, eindex, edcrc, ewa1, eoffset, esize, esize2, _w2, ename = \
                struct.unpack_from('<HHHHIII44s16s', self.hdr_plain, off)
            self.entries.append(dict(
                hdr_off=off, type=etype, index=eindex, crc=edcrc,
                off=eoffset, size=esize, size2=esize2,
                name=ename.split(b'\0')[0].decode('ascii', 'replace')))

        # decoupage du fichier
        self.flash_entry = next(e for e in self.entries if e['type'] == 0)
        fl = self.flash_entry
        self.pad      = raw[NBLOCKS*BLOCK : fl['off'] + self.offskew]
        self.flashbin = bytearray(raw[fl['off']+self.offskew :
                                     fl['off']+self.offskew+fl['size']])
        self.rest     = raw[fl['off']+self.offskew+fl['size'] :]
        if len(self.flashbin) != fl['size']:
            raise ValueError('flash.bin tronque')

    # ------------------------------------------------------------------ CRCs
    def selfcheck(self) -> bool:
        ok = True
        c = jl_crc16(bytes(self.hdr_plain[2:0x40]))
        s, = struct.unpack_from('<H', self.hdr_plain, 0)
        ok &= self._rep(s == c, f'UFW hdrcrc    {s:04X}/{c:04X}')
        c = jl_crc16(bytes(self.hdr_crypt[0x40:self.headersize]))
        s, = struct.unpack_from('<H', self.hdr_plain, 2)
        ok &= self._rep(s == c, f'UFW listcrc   {s:04X}/{c:04X}')
        fl = self.flash_entry
        c = jl_crc16(bytes(self.flashbin))
        ok &= self._rep(fl['crc'] == c, f'UFW flash crc {fl["crc"]:04X}/{c:04X}')

        # uboot.boot : edcrc sur donnees DEBROUILLEES
        ub = bytearray(self.flashbin)
        descramble_bankcb(ub, 0xA0, HEADERKEY)
        hdr32 = bytearray(self.flashbin[0x20:0x40])
        jl_enc_cipher(hdr32, 0, 32, HEADERKEY)
        _e, eoff, esize, _f, _r, _i, _n = struct.unpack_from('<HIIBBH16s', hdr32, 2)
        c = jl_crc16(bytes(ub[eoff:eoff+esize]))
        s = self._crc_of(0x20)
        ok &= self._rep(s == c, f'uboot edcrc    {s:04X}/{c:04X}')

        # isd_config.ini : edcrc sur donnees stockees (clair)
        hdr32 = bytearray(self.flashbin[0x40:0x60])
        jl_enc_cipher(hdr32, 0, 32, HEADERKEY)
        _e, eoff, esize, _f, _r, _i, _n = struct.unpack_from('<HIIBBH16s', hdr32, 2)
        c = jl_crc16(bytes(self.flashbin[eoff:eoff+esize]))
        ok &= self._rep(self._crc_of(0x40) == c, f'isd_config edcrc {self._crc_of(0x40):04X}/{c:04X}')
        return ok

    def _crc_of(self, top_entry_off: int) -> int:
        """edcrc stocke d'une entree top-level."""
        hdr32 = bytearray(self.flashbin[top_entry_off:top_entry_off+32])
        jl_enc_cipher(hdr32, 0, 32, HEADERKEY)
        e, = struct.unpack_from('<H', hdr32, 2)
        return e

    @staticmethod
    def _rep(cond, msg):
        print(f'  [{"OK " if cond else "!!!"}] {msg}')
        return bool(cond)

    # ------------------------------------------------------------- zone app
    def decrypt_app_area(self, chipkey: int):
        jl_sfc_cipher(self.flashbin, APP_BASE, APP_END - APP_BASE,
                      APP_BASE, chipkey)

    def encrypt_app_area(self, chipkey: int):
        # les chiffrements JieLi sont des flux XOR symetriques
        self.decrypt_app_area(chipkey)

    def app_entries(self):
        """Entrees fichier de la zone app (flashbin doit etre dechiffre)."""
        out = []
        for hdr_off in range(APP_BASE + 0x20, APP_BASE + 0x100, 0x20):
            raw = self.flashbin[hdr_off+2:hdr_off+32]
            _e, eoff, esize, flags, _r, idx, ename = \
                struct.unpack_from('<HIIBBH16s', raw, 0)
            out.append(dict(hdr_off=hdr_off, data_off=APP_BASE + eoff,
                            size=esize, flags=flags, index=idx,
                            name=ename.split(b'\0')[0].decode('ascii', 'replace')))
        return out

    def fix_jlfs_entry(self, hdr_off: int, data_off: int, size: int) -> int:
        """Recalcule edcrc (16 bits) puis hcrc d'une entree JLFS (donnees en clair)."""
        edcrc = jl_crc16(bytes(self.flashbin[data_off:data_off+size]))
        struct.pack_into('<H', self.flashbin, hdr_off + 2, edcrc & 0xFFFF)
        hcrc = jl_crc16(bytes(self.flashbin[hdr_off+2:hdr_off+32]))
        struct.pack_into('<H', self.flashbin, hdr_off, hcrc)
        return edcrc

    def fix_app_area_crcs(self, names):
        """Recalcule les CRC des fichiers modifies + de app_area_head."""
        ents = {e['name']: e for e in self.app_entries()}
        for name in names:
            e = ents[name]
            crc = self.fix_jlfs_entry(e['hdr_off'], e['data_off'], e['size'])
            print(f'  entree {name}: edcrc={crc:04X} (recalcule)')
        # app_area_head : CRC sur les donnees qui suivent son en-tete
        #   (data_size = size - 32, soit 0x4020..0x705E7)
        head_off = APP_BASE
        _e, _o, size, _f, _r, _i, _n = \
            struct.unpack_from('<HIIBBH16s', self.flashbin, head_off + 2)
        crc = self.fix_jlfs_entry(head_off, head_off + 32, size - 32)
        print(f'  app_area_head: edcrc={crc:04X} (recalcule, {size-32} o)')

    def fix_isd_config_crcs(self):
        hdr32 = bytearray(self.flashbin[0x40:0x60])
        jl_enc_cipher(hdr32, 0, 32, HEADERKEY)
        _e, eoff, esize, _f, _r, _i, _n = struct.unpack_from('<HIIBBH16s', hdr32, 2)
        edcrc = jl_crc16(bytes(self.flashbin[eoff:eoff+esize]))
        struct.pack_into('<H', hdr32, 2, edcrc & 0xFFFF)
        hcrc = jl_crc16(bytes(hdr32[2:32]))
        struct.pack_into('<H', hdr32, 0, hcrc)
        jl_enc_cipher(hdr32, 0, 32, HEADERKEY)
        self.flashbin[0x40:0x60] = hdr32
        print(f'  entree isd_config.ini: edcrc={edcrc:04X} (recalcule)')

    # ------------------------------------------------------------ conteneur
    def fix_container_crcs(self):
        """edcrc flash.bin, puis rechiffrement des chunks, listcrc, hdrcrc."""
        fl = self.flash_entry
        new_edcrc = jl_crc16(bytes(self.flashbin))
        struct.pack_into('<I', self.hdr_plain, fl['hdr_off'] + 4, new_edcrc & 0xFFFF)
        # rechiffrer les chunks d'entrees (cle fraiche par chunk)
        for off in range(0x40, self.headersize, 0x50):
            chunk = bytearray(self.hdr_plain[off:off+0x50])
            jl_enc_cipher(chunk, 0, 0x50, HEADERKEY)
            self.hdr_crypt[off:off+0x50] = chunk
        # listcrc sur les octets CHIFFRES
        listcrc = jl_crc16(bytes(self.hdr_crypt[0x40:self.headersize]))
        # ecrire listcrc d'abord : il est couvert par hdrcrc ([2:0x40])
        struct.pack_into('<H', self.hdr_plain, 2, listcrc)
        # puis hdrcrc sur les octets DECHIFFRES [2:0x40]
        hdrcrc = jl_crc16(bytes(self.hdr_plain[2:0x40]))
        struct.pack_into('<H', self.hdr_plain, 0, hdrcrc)
        # rechiffrer le premier chunk
        chunk = bytearray(self.hdr_plain[:0x40])
        jl_enc_cipher(chunk, 0, 0x40, HEADERKEY)
        self.hdr_crypt[:0x40] = chunk
        print(f'  conteneur: flash edcrc={new_edcrc & 0xFFFF:04X}, '
              f'listcrc={listcrc:04X}, hdrcrc={hdrcrc:04X}')

    # ----------------------------------------------------------------- sortie
    def emit(self) -> bytes:
        out = bytearray()
        for i in range(NBLOCKS):
            out += self.hdr_crypt[i*KEEP:(i+1)*KEEP]
            out += bytes([self.junk[i]])
        out += self.pad
        out += self.flashbin
        out += self.rest
        if len(out) != len(self.raw):
            raise ValueError(f'taille finale {len(out)} != originale {len(self.raw)}')
        return bytes(out)


def replace_same_size(cur: bytearray, src: bytes, what: str) -> bool:
    if len(src) != len(cur):
        raise ValueError(f'{what}: taille {len(src)} != requise {len(cur)} '
                         '(seuls les patches de meme taille sont supportes)')
    if src == bytes(cur):
        print(f'  {what}: identique (aucun changement)')
        return False
    cur[:] = src
    print(f'  {what}: remplace ({len(src)} o)')
    return True


def find_chipkey(flashbin: bytes) -> int:
    from jltech.chipkeybin import chipkeybin_decode
    ckdata, _c = struct.unpack_from('<32sH', bytes(flashbin), ISD_OFF)
    return chipkeybin_decode(ckdata)


def main():
    ap = argparse.ArgumentParser(description='Repacker .fwsc JieLi new-fw (FM-1)')
    ap.add_argument('input', type=Path)
    ap.add_argument('--app-bin', type=Path, help='app.bin de remplacement (meme taille)')
    ap.add_argument('--cfg-tool', type=Path, help='cfg_tool.bin de remplacement (meme taille)')
    ap.add_argument('--isd-config', type=Path, help='isd_config.ini de remplacement (meme taille)')
    ap.add_argument('--patch', action='append', default=[],
                    help='patch sur la zone app dechiffree : ADRESSE:HEX '
                         '(adresse = offset dans decrypted.bin)')
    ap.add_argument('--chipkey', type=lambda s: int(s, 0), default=None)
    ap.add_argument('--check', action='store_true', help='verifie le modele CRC puis quitte')
    ap.add_argument('--out', type=Path, help='fichier .fwsc de sortie')
    args = ap.parse_args()

    print(f'=== Chargement {args.input}')
    fw = Fwsc(args.input.read_bytes())
    print(f'  chip: {fw.chipname}  imgsize: {fw.imgsize}  '
          f'entries: {[e["name"] for e in fw.entries]}')
    print("=== Verification du modele CRC sur l'original :")
    if not fw.selfcheck():
        print('!!! modele invalide, abandon')
        return 1
    if args.check:
        return 0

    chipkey = args.chipkey if args.chipkey is not None else find_chipkey(fw.flashbin)
    print(f'=== chipkey: {chipkey:04X}')

    print(f'=== Dechiffrement zone app [0x{APP_BASE:X}-0x{APP_END:X})')
    fw.decrypt_app_area(chipkey)
    ents = {e['name']: e for e in fw.app_entries()}

    changed = []
    if args.app_bin:
        e = ents['app.bin']
        cur = bytearray(fw.flashbin[e['data_off']:e['data_off']+e['size']])
        if replace_same_size(cur, args.app_bin.read_bytes(), 'app.bin'):
            fw.flashbin[e['data_off']:e['data_off']+e['size']] = cur
            changed.append('app.bin')
    if args.cfg_tool:
        e = ents['cfg_tool.bin']
        cur = bytearray(fw.flashbin[e['data_off']:e['data_off']+e['size']])
        if replace_same_size(cur, args.cfg_tool.read_bytes(), 'cfg_tool.bin'):
            fw.flashbin[e['data_off']:e['data_off']+e['size']] = cur
            changed.append('cfg_tool.bin')
    if args.isd_config:
        cur = bytearray(fw.flashbin[ISD_OFF:ISD_OFF+ISD_SIZE])
        if replace_same_size(cur, args.isd_config.read_bytes(), 'isd_config.ini'):
            fw.flashbin[ISD_OFF:ISD_OFF+ISD_SIZE] = cur
            changed.append('isd_config.ini')
    if args.patch:
        for spec in args.patch:
            addr_s, hexs = spec.split(':', 1)
            addr, blob = int(addr_s, 0), bytes.fromhex(hexs)
            if addr < APP_BASE or addr + len(blob) > APP_END:
                raise ValueError(f'patch @{addr:#x} hors zone app')
            fw.flashbin[addr:addr+len(blob)] = blob
            print(f'  patch @{addr:#x}: {len(blob)} o')
            changed.append(f'patch@{addr:#x}')
        changed.append('app.bin')  # les patches touchent la zone app par definition

    if not changed:
        print('=== aucun changement : mode aller-retour')
        fw.encrypt_app_area(chipkey)
        data = fw.emit()
        if data == fw.raw:
            print('=== ROUNDTRIP OK : sortie identique a l\'original octet pour octet')
        else:
            nd = sum(1 for a, b in zip(data, fw.raw) if a != b)
            print(f'!!! ROUNDTRIP ECHEC : {nd} octets differents')
            return 1
        if args.out:
            args.out.write_bytes(data)
        return 0

    print('=== Recalcul des CRC de la zone app :')
    app_names = [n for n in ('app.bin', 'cfg_tool.bin')
                 if any(n == c or c.startswith('patch@') for c in changed)]
    if 'isd_config.ini' in changed:
        fw.fix_isd_config_crcs()
    fw.fix_app_area_crcs(app_names)
    fw.encrypt_app_area(chipkey)
    print('=== Recalcul des CRC du conteneur :')
    fw.fix_container_crcs()

    data = fw.emit()
    out = args.out or args.input.with_suffix('.MOD.fwsc')
    out.write_bytes(data)
    print(f'=== Ecrit {out} ({len(data)} o)')

    print('=== Auto-verification de la sortie :')
    fw2 = Fwsc(data)
    if fw2.selfcheck():
        print('=== Tous les CRC de la sortie sont valides.')
        return 0
    print('!!! CRC de sortie invalides !')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
