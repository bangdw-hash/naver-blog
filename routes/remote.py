# -*- coding: utf-8 -*-
"""
remote.py - 모바일 원격 접속 + QR 코드 생성
/remote-control  : QR 코드 페이지
/api/qr-image    : QR PNG 이미지 스트리밍
/api/local-ip    : 현재 PC의 WiFi IP 반환
"""
import os, io, socket
from flask import Blueprint, render_template, jsonify, send_file, request

remote_bp = Blueprint("remote", __name__)


def _get_local_ip() -> str:
    """WiFi(로컬 네트워크) IP 반환. 실패 시 127.0.0.1"""
    try:
        # 외부로 UDP 소켓을 열어 인터페이스 IP 감지 (실제 패킷 안 보냄)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


@remote_bp.route("/remote-control")
def remote_control():
    port = int(os.getenv("PORT", 5000))
    ip   = _get_local_ip()
    url  = f"http://{ip}:{port}"
    return render_template("remote_control.html", local_url=url, ip=ip, port=port)


@remote_bp.route("/api/local-ip")
def local_ip():
    port = int(os.getenv("PORT", 5000))
    ip   = _get_local_ip()
    return jsonify({
        "ip":   ip,
        "port": port,
        "url":  f"http://{ip}:{port}"
    })


@remote_bp.route("/api/qr-image")
def qr_image():
    """쿼리 파라미터 ?url= 또는 현재 앱 URL로 QR PNG 생성"""
    target_url = request.args.get("url", "")
    if not target_url:
        port = int(os.getenv("PORT", 5000))
        ip   = _get_local_ip()
        target_url = f"http://{ip}:{port}"

    try:
        import qrcode
        from qrcode.image.styledpil import StyledPilImage
        from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=12,
            border=3,
        )
        qr.add_data(target_url)
        qr.make(fit=True)

        try:
            # 둥근 스타일 QR
            img = qr.make_image(
                image_factory=StyledPilImage,
                module_drawer=RoundedModuleDrawer()
            )
        except Exception:
            img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png",
                         download_name="qr.png", as_attachment=False)

    except Exception as e:
        # qrcode 없거나 오류 → 1×1 투명 PNG 반환
        import struct, zlib
        def _mini_png():
            sig  = b'\x89PNG\r\n\x1a\n'
            ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
            ihdr_crc = zlib.crc32(b'IHDR' + ihdr) & 0xffffffff
            idat_data = zlib.compress(b'\x00\xff\xff\xff')
            idat_crc  = zlib.crc32(b'IDAT' + idat_data) & 0xffffffff
            iend_crc  = zlib.crc32(b'IEND') & 0xffffffff
            return (sig
                + struct.pack('>I', 13) + b'IHDR' + ihdr + struct.pack('>I', ihdr_crc)
                + struct.pack('>I', len(idat_data)) + b'IDAT' + idat_data + struct.pack('>I', idat_crc)
                + struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc))
        return send_file(io.BytesIO(_mini_png()), mimetype="image/png")
