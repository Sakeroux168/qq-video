"""三种风格样图：微波炉里水分子转动加热。输出 HTML，再由 shot.js 截图。"""
import math, os

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, '..', 'fonts')

W, H = 1080, 1920
# 公共构图
MW = dict(x=110, y=440, w=860, h=520)          # 微波炉
WIN = dict(x=150, y=480, w=560, h=440)         # 门窗
BOWL = (430, 820)                              # 碗口中心
LENS = (600, 1230, 240)                        # 放大圈
MOLS = [(-105, -90, 20), (115, -35, 150), (-25, 130, 260)]  # 相对圈心 + 朝向角


def font_css():
    return f"""
@font-face {{ font-family: NotoBlack; src: url('file://{FONTS}/NotoSansSC-Black.otf'); }}
@font-face {{ font-family: NotoBold; src: url('file://{FONTS}/NotoSansSC-Bold.otf'); }}
@font-face {{ font-family: NotoMed; src: url('file://{FONTS}/NotoSansSC-Medium.otf'); }}
@font-face {{ font-family: KuaiLe; src: url('file://{FONTS}/ZCOOLKuaiLe-Regular.ttf'); }}
html,body {{ margin:0; padding:0; width:{W}px; height:{H}px; overflow:hidden; }}
"""


def sine(x0, x1, y, amp, period, step=6):
    pts = []
    x = x0
    while x <= x1:
        pts.append(f"{x:.1f},{y + amp * math.sin((x - x0) / period * 2 * math.pi):.1f}")
        x += step
    return "M" + " L".join(pts)


def vwave(x, y0, y1, amp, period, step=4):
    pts = []
    y = y0
    while y >= y1:
        pts.append(f"{x + amp * math.sin((y0 - y) / period * 2 * math.pi):.1f},{y:.1f}")
        y -= step
    return "M" + " L".join(pts)


def arc_arrow(cx, cy, r, a0, a1, head):
    """圆弧 + 箭头三角（角度：度，顺时针为正）"""
    p = lambda a: (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
    x0, y0 = p(a0)
    x1, y1 = p(a1)
    large = 1 if (a1 - a0) % 360 > 180 else 0
    path = f"M{x0:.1f},{y0:.1f} A{r},{r} 0 {large} 1 {x1:.1f},{y1:.1f}"
    # 箭头：沿切线方向
    t = math.radians(a1)
    tx, ty = -math.sin(t), math.cos(t)          # 顺时针切线
    nx, ny = math.cos(t), math.sin(t)
    tip = (x1 + tx * head * 1.1, y1 + ty * head * 1.1)
    b1 = (x1 + nx * head * 0.75, y1 + ny * head * 0.75)
    b2 = (x1 - nx * head * 0.75, y1 - ny * head * 0.75)
    tri = f"M{tip[0]:.1f},{tip[1]:.1f} L{b1[0]:.1f},{b1[1]:.1f} L{b2[0]:.1f},{b2[1]:.1f} Z"
    return path, tri


def mol_pos(i):
    dx, dy, ang = MOLS[i]
    return LENS[0] + dx, LENS[1] + dy, ang


def h_pos(cx, cy, ang, d):
    out = []
    for s in (-52, 52):
        a = math.radians(ang + s)
        out.append((cx + d * math.cos(a), cy + d * math.sin(a)))
    return out


def lens_tangents(px, py, cx, cy, r):
    """从碗口点到放大圈的两条切线切点"""
    dx, dy = px - cx, py - cy
    d = math.hypot(dx, dy)
    base = math.atan2(dy, dx)
    off = math.acos(r / d)
    return [(cx + r * math.cos(base + s * off), cy + r * math.sin(base + s * off)) for s in (-1, 1)]


# ---------------------------------------------------------------- 1 贴纸风
def style_sticker():
    K = '#222222'; Y = '#FFC83D'; R = '#FF5C5C'; B = '#4AA8FF'; BG = '#FFF3D9'; WT = '#FFFFFF'
    sw = 10
    lx, ly, lr = LENS
    t1, t2 = lens_tangents(BOWL[0], BOWL[1] + 20, lx, ly, lr)
    g = []
    # 放大连线（在微波炉下层）
    g.append(f'<path d="M{BOWL[0]-70},{BOWL[1]+40} L{t1[0]:.0f},{t1[1]:.0f} L{t2[0]:.0f},{t2[1]:.0f} L{BOWL[0]+70},{BOWL[1]+40} Z" fill="{Y}" opacity="0.45"/>')
    # 微波炉：脚
    for fx in (200, 880):
        g.append(f'<rect x="{fx-30}" y="950" width="60" height="40" rx="12" fill="{K}"/>')
    # 硬投影 + 机身
    g.append(f'<rect x="{MW["x"]+14}" y="{MW["y"]+14}" width="{MW["w"]}" height="{MW["h"]}" rx="48" fill="{K}"/>')
    g.append(f'<rect x="{MW["x"]}" y="{MW["y"]}" width="{MW["w"]}" height="{MW["h"]}" rx="48" fill="{B}" stroke="{K}" stroke-width="{sw}"/>')
    # 门窗
    g.append(f'<rect x="{WIN["x"]}" y="{WIN["y"]}" width="{WIN["w"]}" height="{WIN["h"]}" rx="30" fill="{BG}" stroke="{K}" stroke-width="{sw}"/>')
    # 微波
    for yy in (545, 610):
        g.append(f'<path d="{sine(190, 670, yy, 18, 80)}" fill="none" stroke="{K}" stroke-width="22" stroke-linecap="round"/>')
        g.append(f'<path d="{sine(190, 670, yy, 18, 80)}" fill="none" stroke="{Y}" stroke-width="10" stroke-linecap="round"/>')
    # 转盘
    g.append(f'<ellipse cx="{BOWL[0]}" cy="895" rx="210" ry="26" fill="{WT}" stroke="{K}" stroke-width="{sw}"/>')
    # 碗 + 米饭
    bx, by = BOWL
    g.append(f'<path d="M{bx-120},{by-15} Q{bx-125},{by-70} {bx-60},{by-80} Q{bx},{by-120} {bx+60},{by-80} Q{bx+125},{by-70} {bx+120},{by-15} Z" fill="{WT}" stroke="{K}" stroke-width="{sw}" stroke-linejoin="round"/>')
    g.append(f'<path d="M{bx-135},{by-15} L{bx+135},{by-15} Q{bx+120},{by+70} {bx},{by+72} Q{bx-120},{by+70} {bx-135},{by-15} Z" fill="{R}" stroke="{K}" stroke-width="{sw}" stroke-linejoin="round"/>')
    # 热气
    for hx in (bx - 50, bx + 5, bx + 60):
        g.append(f'<path d="{vwave(hx, by-125, by-175, 9, 50)}" fill="none" stroke="{R}" stroke-width="10" stroke-linecap="round"/>')
    # 控制面板
    g.append(f'<rect x="750" y="500" width="170" height="80" rx="16" fill="{K}"/>')
    g.append(f'<text x="835" y="560" font-family="KuaiLe" font-size="52" fill="{Y}" text-anchor="middle">1:30</text>')
    for ky in (680, 820):
        g.append(f'<circle cx="835" cy="{ky}" r="52" fill="{WT}" stroke="{K}" stroke-width="{sw}"/>')
        g.append(f'<rect x="829" y="{ky-38}" width="12" height="36" rx="6" fill="{K}"/>')
    # 放大圈
    g.append(f'<circle cx="{lx+12}" cy="{ly+12}" r="{lr}" fill="{K}"/>')
    g.append(f'<circle cx="{lx}" cy="{ly}" r="{lr}" fill="{WT}" stroke="{K}" stroke-width="{sw+2}"/>')
    for i in range(3):
        cx, cy, ang = mol_pos(i)
        p, tri = arc_arrow(cx, cy, 92, ang + 120, ang + 300, 20)
        g.append(f'<path d="{p}" fill="none" stroke="{K}" stroke-width="20" stroke-linecap="round"/>')
        g.append(f'<path d="{p}" fill="none" stroke="{B}" stroke-width="9" stroke-linecap="round"/>')
        g.append(f'<path d="{tri}" fill="{B}" stroke="{K}" stroke-width="6" stroke-linejoin="round"/>')
        for hx, hy in h_pos(cx, cy, ang, 54):
            g.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="24" fill="{WT}" stroke="{K}" stroke-width="8"/>')
        g.append(f'<circle cx="{cx}" cy="{cy}" r="42" fill="{R}" stroke="{K}" stroke-width="8"/>')
        g.append(f'<circle cx="{cx-13}" cy="{cy-4}" r="6" fill="{K}"/><circle cx="{cx+13}" cy="{cy-4}" r="6" fill="{K}"/>')
        g.append(f'<path d="M{cx-10},{cy+12} Q{cx},{cy+22} {cx+10},{cy+12}" fill="none" stroke="{K}" stroke-width="5" stroke-linecap="round"/>')

    def tag(cx, cy, text, size, fill, color=K, rot=0):
        w = len(text) * size + 70
        h = size + 50
        return (f'<g transform="rotate({rot} {cx} {cy})">'
                f'<rect x="{cx-w/2+10}" y="{cy-h/2+10}" width="{w}" height="{h}" rx="{h/2}" fill="{K}"/>'
                f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="{h/2}" fill="{fill}" stroke="{K}" stroke-width="{sw}"/>'
                f'<text x="{cx}" y="{cy+size*0.36}" font-family="KuaiLe" font-size="{size}" fill="{color}" text-anchor="middle">{text}</text></g>')
    g.append(tag(300, 440, '微波', 80, Y, rot=-4))
    g.append(tag(220, 1020, '水分子', 80, WT, rot=-6))
    head = (f'<text x="540" y="320" font-family="KuaiLe" font-size="120" text-anchor="middle" '
            f'fill="{WT}" stroke="{K}" stroke-width="22" stroke-linejoin="round" paint-order="stroke">疯狂转圈 → <tspan fill="{R}">发热</tspan></text>')
    body = f'<rect width="{W}" height="{H}" fill="{BG}"/>' + ''.join(g) + head
    return body


# ---------------------------------------------------------------- 2 扁平 MG
def style_flat():
    N = '#23305A'; N2 = '#1A2546'; C = '#FF6F59'; T = '#43C6AC'; CR = '#FFF4E0'
    lx, ly, lr = LENS
    t1, t2 = lens_tangents(BOWL[0], BOWL[1] + 20, lx, ly, lr)
    g = []
    g.append(f'<path d="M{BOWL[0]-90},{BOWL[1]+30} L{t1[0]:.0f},{t1[1]:.0f} L{t2[0]:.0f},{t2[1]:.0f} L{BOWL[0]+90},{BOWL[1]+30} Z" fill="{CR}" opacity="0.10"/>')
    # 机身
    g.append(f'<rect x="{MW["x"]}" y="{MW["y"]}" width="{MW["w"]}" height="{MW["h"]}" rx="36" fill="{CR}"/>')
    g.append(f'<rect x="{MW["x"]}" y="{MW["y"]+MW["h"]-36}" width="{MW["w"]}" height="36" fill="{CR}"/>')
    g.append(f'<rect x="150" y="{MW["y"]+MW["h"]}" width="80" height="24" fill="{N2}"/><rect x="850" y="{MW["y"]+MW["h"]}" width="80" height="24" fill="{N2}"/>')
    g.append(f'<rect x="{WIN["x"]}" y="{WIN["y"]}" width="{WIN["w"]}" height="{WIN["h"]}" rx="24" fill="{N2}"/>')
    for yy in (545, 610):
        g.append(f'<path d="{sine(190, 670, yy, 20, 90)}" fill="none" stroke="{T}" stroke-width="12" stroke-linecap="round"/>')
    g.append(f'<rect x="{BOWL[0]-200}" y="885" width="400" height="16" rx="8" fill="{N}"/>')
    bx, by = BOWL
    g.append(f'<path d="M{bx-115},{by-15} A115,88 0 0 1 {bx+115},{by-15} Z" fill="{CR}"/>')
    g.append(f'<path d="M{bx-135},{by-15} L{bx+135},{by-15} A135,85 0 0 1 {bx-135},{by-15} Z" fill="{C}"/>')
    g.append(f'<rect x="{bx-45}" y="{by+62}" width="90" height="14" fill="{C}"/>')
    for hx in (bx - 45, bx + 45):
        g.append(f'<path d="{vwave(hx, by-110, by-170, 9, 55)}" fill="none" stroke="{C}" stroke-width="10" stroke-linecap="round"/>')
    # 面板
    g.append(f'<rect x="750" y="500" width="170" height="80" rx="12" fill="{N2}"/>')
    g.append(f'<text x="835" y="558" font-family="NotoBlack" font-size="46" fill="{T}" text-anchor="middle">1:30</text>')
    for ky in (680, 820):
        g.append(f'<circle cx="835" cy="{ky}" r="50" fill="{T}"/>')
        g.append(f'<rect x="829" y="{ky-38}" width="12" height="34" rx="6" fill="{N2}"/>')
    # 放大圈
    g.append(f'<circle cx="{lx}" cy="{ly}" r="{lr}" fill="{T}"/>')
    g.append(f'<circle cx="{lx}" cy="{ly}" r="{lr-16}" fill="{N2}"/>')
    for i in range(3):
        cx, cy, ang = mol_pos(i)
        p, tri = arc_arrow(cx, cy, 92, ang + 120, ang + 300, 20)
        g.append(f'<path d="{p}" fill="none" stroke="{T}" stroke-width="10" stroke-linecap="round"/>')
        g.append(f'<path d="{tri}" fill="{T}"/>')
        for hx, hy in h_pos(cx, cy, ang, 54):
            g.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="25" fill="{CR}"/>')
        g.append(f'<circle cx="{cx}" cy="{cy}" r="42" fill="{C}"/>')

    def chip(cx, cy, text, size, fill, color):
        w = len(text) * size + 64
        h = size + 40
        return (f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="16" fill="{fill}"/>'
                f'<text x="{cx}" y="{cy+size*0.36}" font-family="NotoBlack" font-size="{size}" fill="{color}" text-anchor="middle">{text}</text>')
    g.append(chip(270, 440, '微波', 72, T, N2))
    g.append(chip(210, 1020, '水分子', 72, C, CR))
    head = (f'<text x="540" y="310" font-family="NotoBlack" font-size="112" text-anchor="middle" fill="{CR}">'
            f'疯狂转圈 → <tspan fill="{C}">发热</tspan></text>')
    return f'<rect width="{W}" height="{H}" fill="{N}"/>' + ''.join(g) + head


# ---------------------------------------------------------------- 3 写实信息图
def style_real():
    BG0 = '#1A212B'; BG1 = '#0B0E12'; CY = '#5CC8FF'; OR = '#FF9A3D'; WT = '#F2F4F7'
    lx, ly, lr = LENS
    t1, t2 = lens_tangents(BOWL[0], BOWL[1] + 20, lx, ly, lr)
    defs = f"""
<defs>
 <radialGradient id="bg" cx="50%" cy="40%" r="75%"><stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/></radialGradient>
 <linearGradient id="metal" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4A525D"/><stop offset="0.5" stop-color="#2E343C"/><stop offset="1" stop-color="#1D2127"/></linearGradient>
 <linearGradient id="panel" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2A2F37"/><stop offset="1" stop-color="#3A414B"/></linearGradient>
 <radialGradient id="cavity" cx="50%" cy="75%" r="80%"><stop offset="0" stop-color="#6B4A22"/><stop offset="0.6" stop-color="#2A2118"/><stop offset="1" stop-color="#121010"/></radialGradient>
 <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.10"/><stop offset="0.35" stop-color="#FFFFFF" stop-opacity="0.02"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
 <pattern id="mesh" width="10" height="10" patternUnits="userSpaceOnUse"><circle cx="5" cy="5" r="1.8" fill="#000" opacity="0.22"/></pattern>
 <linearGradient id="bowl" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#9AA3AD"/><stop offset="0.45" stop-color="#F4F6F8"/><stop offset="1" stop-color="#B7BEC6"/></linearGradient>
 <radialGradient id="rice" cx="45%" cy="30%" r="70%"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#D8D2C4"/></radialGradient>
 <radialGradient id="O" cx="35%" cy="30%" r="70%"><stop offset="0" stop-color="#FFB27A"/><stop offset="0.55" stop-color="#E8562A"/><stop offset="1" stop-color="#7A1E0C"/></radialGradient>
 <radialGradient id="H" cx="35%" cy="30%" r="70%"><stop offset="0" stop-color="#FFFFFF"/><stop offset="0.6" stop-color="#C9D1DA"/><stop offset="1" stop-color="#6C7681"/></radialGradient>
 <radialGradient id="lensbg" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#16202B"/><stop offset="1" stop-color="#0C1218"/></radialGradient>
 <filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="shadow" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="24" stdDeviation="22" flood-color="#000" flood-opacity="0.6"/></filter>
 <clipPath id="win"><rect x="{WIN['x']}" y="{WIN['y']}" width="{WIN['w']}" height="{WIN['h']}" rx="14"/></clipPath>
</defs>"""
    g = []
    g.append(f'<path d="M{BOWL[0]-80},{BOWL[1]+40} L{t1[0]:.0f},{t1[1]:.0f} M{BOWL[0]+80},{BOWL[1]+40} L{t2[0]:.0f},{t2[1]:.0f}" stroke="{CY}" stroke-width="2.5" stroke-dasharray="10 10" opacity="0.7"/>')
    g.append(f'<rect x="{MW["x"]}" y="{MW["y"]}" width="{MW["w"]}" height="{MW["h"]}" rx="22" fill="url(#metal)" filter="url(#shadow)"/>')
    g.append(f'<rect x="{MW["x"]+3}" y="{MW["y"]+3}" width="{MW["w"]-6}" height="4" rx="2" fill="#FFFFFF" opacity="0.18"/>')
    g.append(f'<rect x="725" y="470" width="215" height="460" rx="10" fill="url(#panel)"/>')
    # 腔体
    g.append(f'<g clip-path="url(#win)"><rect x="{WIN["x"]}" y="{WIN["y"]}" width="{WIN["w"]}" height="{WIN["h"]}" fill="url(#cavity)"/>')
    g.append(f'<ellipse cx="{BOWL[0]}" cy="892" rx="215" ry="26" fill="#3A3F45"/><ellipse cx="{BOWL[0]}" cy="888" rx="215" ry="24" fill="#5A6068" opacity="0.6"/>')
    bx, by = BOWL
    g.append(f'<ellipse cx="{bx}" cy="{by-15}" rx="118" ry="22" fill="url(#rice)"/>')
    g.append(f'<path d="M{bx-115},{by-15} Q{bx-110},{by-90} {bx},{by-95} Q{bx+110},{by-90} {bx+115},{by-15} Z" fill="url(#rice)"/>')
    g.append(f'<path d="M{bx-130},{by-15} Q{bx-120},{by+70} {bx},{by+72} Q{bx+120},{by+70} {bx+130},{by-15} Z" fill="url(#bowl)"/>')
    g.append(f'<ellipse cx="{bx}" cy="{by-15}" rx="130" ry="10" fill="none" stroke="#FFFFFF" stroke-opacity="0.6" stroke-width="3"/>')
    for yy, op in ((545, 0.95), (610, 0.7)):
        g.append(f'<path d="{sine(170, 690, yy, 16, 70)}" fill="none" stroke="{CY}" stroke-width="4" opacity="{op}" filter="url(#soft)"/>')
    for hx in (bx - 45, bx + 10, bx + 60):
        g.append(f'<path d="{vwave(hx, by-110, by-170, 8, 60)}" fill="none" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round" opacity="0.35"/>')
    g.append(f'<rect x="{WIN["x"]}" y="{WIN["y"]}" width="{WIN["w"]}" height="{WIN["h"]}" fill="url(#mesh)"/>')
    g.append(f'<rect x="{WIN["x"]}" y="{WIN["y"]}" width="{WIN["w"]}" height="{WIN["h"]}" fill="url(#glass)"/></g>')
    g.append(f'<rect x="{WIN["x"]}" y="{WIN["y"]}" width="{WIN["w"]}" height="{WIN["h"]}" rx="14" fill="none" stroke="#11151A" stroke-width="8"/>')
    # 面板细节
    g.append(f'<rect x="752" y="505" width="162" height="70" rx="6" fill="#0A0C0F"/>')
    g.append(f'<text x="833" y="557" font-family="NotoBold" font-size="44" fill="{OR}" text-anchor="middle" letter-spacing="4">1:30</text>')
    for ky in (690, 830):
        g.append(f'<circle cx="833" cy="{ky}" r="50" fill="#1A1E23"/><circle cx="833" cy="{ky}" r="44" fill="url(#metal)"/>')
        g.append(f'<rect x="830" y="{ky-38}" width="6" height="26" rx="3" fill="#C9D1DA"/>')
    # 放大圈
    g.append(f'<circle cx="{lx}" cy="{ly}" r="{lr}" fill="url(#lensbg)"/>')
    g.append(f'<circle cx="{lx}" cy="{ly}" r="{lr}" fill="none" stroke="{CY}" stroke-width="4" filter="url(#soft)"/>')
    for i in range(3):
        cx, cy, ang = mol_pos(i)
        p, tri = arc_arrow(cx, cy, 92, ang + 120, ang + 300, 14)
        g.append(f'<path d="{p}" fill="none" stroke="{CY}" stroke-width="4" stroke-linecap="round" opacity="0.9"/>')
        g.append(f'<path d="{tri}" fill="{CY}"/>')
        for hx, hy in h_pos(cx, cy, ang, 54):
            g.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="25" fill="url(#H)"/>')
        g.append(f'<circle cx="{cx}" cy="{cy}" r="42" fill="url(#O)"/>')

    def label(px, py, tx, ty, text, size, anchor='start'):
        # 引线 + 端点 + 文字 + 左侧色条
        s = (f'<circle cx="{px}" cy="{py}" r="9" fill="{CY}"/>'
             f'<path d="M{px},{py} L{tx},{ty}" stroke="{CY}" stroke-width="3"/>')
        if anchor == 'start':
            s += f'<rect x="{tx}" y="{ty-size*0.82}" width="8" height="{size*1.0}" fill="{CY}"/>'
            s += f'<text x="{tx+26}" y="{ty}" font-family="NotoBold" font-size="{size}" fill="{WT}">{text}</text>'
        else:
            s += f'<rect x="{tx-8}" y="{ty-size*0.82}" width="8" height="{size*1.0}" fill="{CY}"/>'
            s += f'<text x="{tx-26}" y="{ty}" font-family="NotoBold" font-size="{size}" fill="{WT}" text-anchor="end">{text}</text>'
        return s
    g.append(label(560, 540, 560, 420, '', 76))
    g.append(f'<text x="586" y="420" font-family="NotoBold" font-size="76" fill="{WT}">微波</text>')
    g.append(f'<rect x="560" y="358" width="8" height="76" fill="{CY}"/>')
    cx, cy, _ = mol_pos(0)
    g.append(label(cx - 42, cy - 30, 330, 1030, '水分子', 76, anchor='end'))
    head = (f'<text x="540" y="300" font-family="NotoBlack" font-size="104" text-anchor="middle" fill="{WT}">'
            f'疯狂转圈 → <tspan fill="{OR}">发热</tspan></text>')
    return defs + f'<rect width="{W}" height="{H}" fill="url(#bg)"/>' + ''.join(g) + head


def page(svg):
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{font_css()}</style></head><body>'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{svg}</svg></body></html>')


if __name__ == '__main__':
    for name, fn in (('1_sticker', style_sticker), ('2_flat', style_flat), ('3_real', style_real)):
        with open(os.path.join(HERE, f'{name}.html'), 'w', encoding='utf-8') as f:
            f.write(page(fn()))
    print('ok')
