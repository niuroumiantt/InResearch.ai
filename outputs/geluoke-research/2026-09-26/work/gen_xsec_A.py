#!/usr/bin/env python3
# Generator for xsec_A.svg  -- side-elevation section of an AI data centre (blueprint style)
# Rev 2: judge fixes 1-11 applied (labels 21px, CDU band filled, dry cooler, sleeves, handhole, grafts...)
W,H=1200,640
WHITE="#F4F6FA"; CYAN="#7FD3FF"; GOLD="#E0B45C"; GREY="#6F86A8"
out=[]
def add(s): out.append(s)
def line(x1,y1,x2,y2,stroke=WHITE,sw=1,op=.8,dash=None,cap="butt",extra=""):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-opacity="{op}" stroke-width="{sw}"{d} stroke-linecap="{cap}"{extra}/>')
def rect(x,y,w,h,stroke=WHITE,sw=1,op=.8,fill="panel",rx=0,extra=""):
    if fill=="panel": f='fill="#FFFFFF" fill-opacity="0.05"'
    elif fill=="none": f='fill="none"'
    else: f=f'fill="{fill}"'
    st='stroke="none"' if stroke is None else f'stroke="{stroke}" stroke-opacity="{op}" stroke-width="{sw}"'
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" {f} {st}{extra}/>')
def path(d,stroke=WHITE,sw=1,op=.8,dash=None,fill="none",cap="butt",join="miter",extra=""):
    ds=f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-opacity="{op}" stroke-width="{sw}"{ds} stroke-linecap="{cap}" stroke-linejoin="{join}"{extra}/>')
def circle(cx,cy,r,stroke=WHITE,sw=1,op=.8,fill="none",fop=1):
    add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" fill-opacity="{fop}" stroke="{stroke}" stroke-opacity="{op}" stroke-width="{sw}"/>')
def ellipse(cx,cy,rx,ry,stroke=WHITE,sw=1,op=.8,fill="none"):
    f='fill="#FFFFFF" fill-opacity="0.05"' if fill=="panel" else f'fill="{fill}"'
    add(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" {f} stroke="{stroke}" stroke-opacity="{op}" stroke-width="{sw}"/>')
def text(x,y,s,size=21,anchor="start",op=.92):
    add(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{WHITE}" fill-opacity="{op}">{s}</text>')
def dot(x,y,r=2.2): add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{WHITE}" fill-opacity=".85" stroke="none"/>')
def sleeve(x,y,w=12,h=4):
    """wall sleeve: short grey tube drawn around a pipe where it penetrates a wall"""
    rect(x,y,w,h,stroke=GREY,sw=1,op=.9,fill="panel")

# ---------- header ----------
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
add('<title>AI数据中心 侧立剖面图</title>')
add('<style>text{font-family:"Noto Sans SC","WenQuanYi Zen Hei",sans-serif;}</style>')
add('<defs>')
add(f'<pattern id="earth" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="10" stroke="{GREY}" stroke-width="1" stroke-opacity=".30"/></pattern>')
add(f'<pattern id="conc" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" stroke="{GREY}" stroke-width="1" stroke-opacity=".55"/></pattern>')
# markers sized in user units so arrowheads stay the same size on thin and thick lines
add(f'<marker id="arrW" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto"><path d="M1,1 L9,5 L1,9" fill="none" stroke="{WHITE}" stroke-opacity=".85" stroke-width="1.3"/></marker>')
add(f'<marker id="arrC" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="11" markerHeight="11" markerUnits="userSpaceOnUse" orient="auto"><path d="M1,1 L9,5 L1,9" fill="none" stroke="{CYAN}" stroke-opacity=".95" stroke-width="1.5"/></marker>')
add('</defs>')

# ---------- key levels ----------
GROUND=482; ROOF_T=165; ROOF_B=175; FLOOR_T=470
OUT_L=306; OUT_R=1010; WALL=8
IN_L=OUT_L+WALL; IN_R=OUT_R-WALL
# rooms
A=(314,424); N=(430,514); B=(520,826); C=(832,1002)
P1=(424,430); P2=(514,520); P3=(826,832)
RF=440  # raised floor top
EARTH_B=540  # bottom of earth hatch

# ---------- corner registration marks ----------
for (x,y,sx,sy) in [(24,24,1,1),(1176,24,-1,1),(24,616,1,-1),(1176,616,-1,-1)]:
    path(f"M{x},{y+14*sy} V{y} H{x+14*sx}",sw=1,op=.55)

# ---------- ground hatch (knock-outs: 光缆出局 label, fibre handhole) ----------
add(f'<path fill="url(#earth)" fill-rule="evenodd" d="M24,{GROUND+2} H1176 V{EARTH_B} H24 Z M46,490 H142 V518 H46 Z M146,{GROUND+2} H166 V532 H146 Z"/>')
line(24,EARTH_B,1176,EARTH_B,sw=1,op=.4,dash="3 5")
# ground line
line(24,GROUND,1176,GROUND,sw=2,op=.85)
# footings
rect(298,GROUND,24,12,sw=1,op=.55,fill="url(#conc)")
rect(994,GROUND,24,12,sw=1,op=.55,fill="url(#conc)")
# fibre handhole: concrete pit from grade down past the duct, hollow inside
add(f'<path d="M146,{GROUND} H166 V532 H146 Z M150,{GROUND+4} H162 V528 H150 Z" fill="url(#conc)" fill-rule="evenodd" stroke="{WHITE}" stroke-opacity=".6" stroke-width="1"/>')
line(143,GROUND,169,GROUND,sw=2.5,op=.85)   # cover frame at grade

# ---------- underground services ----------
# fibre conduit (network room -> handhole -> left edge)
path("M446,440 V526 H40",stroke=WHITE,sw=1.4,op=.85,dash="1.5 3.5",cap="round",extra=' marker-end="url(#arrW)"')
text(52,510,"光缆出局")
# LV cable trench transformer -> switchgear
path("M168,462 H176 V500 H348 V470",stroke=GOLD,sw=1.6,op=.95)
# water main (right edge -> riser -> tower make-up)
path("M1176,546 H1166 V140 H996",stroke=CYAN,sw=1.1,op=.9,extra=' marker-end="url(#arrC)"')
path("M1161,514 L1171,522 L1161,530 Z M1171,514 L1161,522 L1171,530 Z",stroke=CYAN,sw=1,op=.9,fill=CYAN)  # valve
line(1176,540,1176,552,stroke=CYAN,sw=1.5,op=.9)
text(1100,560,"供水")
path("M1147,553 L1158,527",sw=1,op=.7); dot(1160,522)   # leader onto valve tip

# ---------- LEFT YARD : 220kV ----------
# gantry
for px in (42,76):
    rect(px,152,6,GROUND-152,sw=1,op=.7)
    for yy in range(160,GROUND-8,16):
        line(px,yy,px+6,yy+8,stroke=GREY,sw=1,op=.7); line(px+6,yy,px,yy+8,stroke=GREY,sw=1,op=.7)
rect(34,146,54,6,sw=1,op=.8)
# insulator strings + incoming conductors + jumpers to bushings
for i,(sx,ey,bx) in enumerate([(48,158,116),(61,163,136),(74,168,156)]):
    line(sx,152,sx,176,stroke=GREY,sw=1.2,op=.85)
    for yy in (157,163,169,175): line(sx-3.5,yy,sx+3.5,yy,stroke=WHITE,sw=1,op=.7)
    path(f"M24,{ey} Q{(24+sx)/2},{ey+(176-ey)*0.75} {sx},176",stroke=GOLD,sw=1.6,op=.95)
    path(f"M{sx},176 C{sx+8},250 {bx-26},{286} {bx},298",stroke=GOLD,sw=1.5,op=.9)
# transformer: radiators, tank, conservator, bushings
line(78,396,96,396,sw=1,op=.7); line(78,462,96,462,sw=1,op=.7)
for fx in (80,84,88,92): line(fx,396,fx,462,stroke=GREY,sw=1.5,op=.85)
rect(96,388,72,GROUND-388,sw=1.4,op=.85)
line(96,410,168,410,stroke=GREY,sw=1,op=.6); line(96,448,168,448,stroke=GREY,sw=1,op=.6)
rect(104,364,60,16,rx=8,sw=1.2,op=.8)
line(134,380,134,388,sw=1,op=.7)
for bx in (116,136,156):
    rect(bx-3,300,6,88,sw=1,op=.75)
    for yy in range(308,384,9): line(bx-5.5,yy,bx+5.5,yy,stroke=WHITE,sw=1,op=.6)
    circle(bx,298,3,stroke=GOLD,sw=1,op=.9,fill=GOLD,fop=.9)
rect(90,FLOOR_T,84,12,sw=1,op=.6,fill="url(#conc)")
text(168,322,"220kV接入"); text(168,344,"主变压器")
path("M176,349 L167,370",sw=1,op=.7); dot(165,372)

# ---------- LEFT YARD : diesel genset + day tank ----------
rect(184,FLOOR_T,108,12,sw=1,op=.6,fill="url(#conc)")                       # shared plinth
rect(188,420,74,50,sw=1.3,op=.85)
for yy in range(428,466,6): line(192,yy,206,yy,stroke=GREY,sw=1,op=.8)      # radiator grille
rect(238,428,18,42,sw=1,op=.6,fill="none"); circle(252,450,1.5,stroke=WHITE,sw=1,op=.7)
line(210,420,210,470,stroke=GREY,sw=1,op=.5); line(232,420,232,470,stroke=GREY,sw=1,op=.5)
rect(246,408,6,12,sw=1,op=.8); rect(242,404,14,4,sw=1,op=.8)               # exhaust stack
path("M262,440 H322",stroke=GOLD,sw=1.6,op=.95)                              # genset feed
# day tank on the plinth, fuel line to the engine
rect(268,448,22,22,rx=3,sw=1.1,op=.8)
line(271,461,287,461,stroke=GREY,sw=1,op=.8,dash="2 2")                     # fuel level
line(285,448,285,443,sw=1,op=.7); line(282,443,288,443,sw=1,op=.7)          # vent
line(262,465,268,465,sw=1,op=.7)                                             # fuel line
text(172,396,"柴油备用发电")
path("M226,402 V418",sw=1,op=.7); dot(226,418)

# ---------- BUILDING SHELL ----------
rect(OUT_L,ROOF_T,OUT_R-OUT_L,ROOF_B-ROOF_T,sw=1.5,op=.85,fill="url(#conc)")   # roof slab
rect(OUT_L,FLOOR_T,OUT_R-OUT_L,GROUND-FLOOR_T,sw=1.5,op=.85,fill="url(#conc)") # floor slab
rect(OUT_L,ROOF_T,WALL,FLOOR_T-ROOF_T,sw=1.5,op=.85,fill="url(#conc)")          # left wall
rect(OUT_R-WALL,ROOF_T,WALL,FLOOR_T-ROOF_T,sw=1.5,op=.85,fill="url(#conc)")     # right wall
for (a,b) in (P1,P2,P3):
    rect(a,ROOF_B,b-a,FLOOR_T-ROOF_B,sw=1,op=.7,fill="url(#conc)")
# level markers (ground / roof) just outside the left wall
LM=299
path(f"M{LM-5},474 L{LM+5},474 L{LM},482 Z",sw=1,op=.8); line(LM-10,482,LM+10,482,sw=1,op=.8)
path(f"M{LM-5},157 L{LM+5},157 L{LM},165 Z",sw=1,op=.8); line(LM-10,165,LM+10,165,sw=1,op=.8)

# wall sleeves (drawn before the pipes so the pipe passes over the sleeve)
sleeve(823,450); sleeve(823,460)          # underfloor headers through CDU wall (826-832)
sleeve(1000,254); sleeve(1000,268)        # primary headers through the right wall (1002-1010)

# raised floor (rooms N and B)
line(N[0],RF,B[1],RF,sw=1.5,op=.8)
for px in range(436,822,34): line(px,RF+2,px,FLOOR_T,stroke=GREY,sw=1,op=.7)

# ---------- ROOM A : MV switchgear / UPS / batteries ----------
for cx in (322,340,358):
    rect(cx,372,16,FLOOR_T-372,sw=1.2,op=.85)
    rect(cx+3,380,10,8,sw=1,op=.6,fill="none"); line(cx,400,cx+16,400,stroke=GREY,sw=1,op=.7)
    circle(cx+8,422,1.5,stroke=WHITE,sw=1,op=.7)
rect(378,380,18,FLOOR_T-380,sw=1.2,op=.85); rect(381,388,12,6,sw=1,op=.6,fill="none")
for yy in (430,436,442,448): line(381,yy,393,yy,stroke=GREY,sw=1,op=.7)
# battery cabinet: 4 x 5 cell matrix
rect(400,340,20,FLOOR_T-340,sw=1.2,op=.85)
for sy in (366,392,418,444,470):
    line(400,sy,420,sy,stroke=GREY,sw=1,op=.8)
    for c in range(4):
        rect(402.5+4*c,sy-12,3,10,sw=1,op=.6,fill="none")
# busway riser + overhead busway
path("M349,372 V244 H812",stroke=GOLD,sw=2.5,op=.95)
rect(345,240,8,8,stroke=GOLD,sw=1,op=.9,fill=GOLD)

# ---------- ROOM N : network / meet-me ----------
for rx0 in (436,460,484):
    rect(rx0,330,20,RF-330,sw=1.2,op=.85)
    for k in range(8):
        yy=340+k*12; line(rx0+3,yy,rx0+17,yy,stroke=GREY,sw=1,op=.8)
        if k%2==0:
            for dx in (5,9,13): circle(rx0+dx,yy+5,1,stroke=WHITE,sw=1,op=.6)
# fibre tray + riser
line(446,230,812,230,stroke=WHITE,sw=1.4,op=.85,dash="1.5 3.5",cap="round")
line(446,230,446,330,stroke=WHITE,sw=1.4,op=.85,dash="1.5 3.5",cap="round")

# ---------- ROOM B : AI hall ----------
PITCH=24
racks=[532+PITCH*k for k in range(5)]+[696+PITCH*k for k in range(5)]
RT=306
# hot-aisle containment (46 px gap between the two banks)
rect(650,RT,46,RF-RT,stroke=None,fill="panel")
line(650,RT,696,RT,sw=1,op=.7); line(673,RT,673,RT+20,stroke=GREY,sw=1,op=.7)
for x0 in racks:
    rect(x0,RT,22,RF-RT,sw=1.2,op=.85)
    for k in range(6):
        yy=312+20*k
        rect(x0+2,yy,14,12,sw=1,op=.6,fill="none")              # tray outline
        line(x0+16,yy+6,x0+18,yy+6,stroke=CYAN,sw=1,op=.9)      # cold-plate stub to manifold
    rect(x0+18,310,2,RF-310,stroke=None,fill=CYAN)              # rack manifold
    line(x0+19,RF,x0+19,452,stroke=CYAN,sw=1,op=.9)             # riser from underfloor header
    line(x0+11,244,x0+11,RT,stroke=GOLD,sw=1,op=.9)             # busway drop
# underfloor coolant headers -> CDU room. Supply flows CDU -> racks (arrow mid-run, in the containment gap)
path("M940,452 H680",stroke=CYAN,sw=2,op=.95,extra=' marker-end="url(#arrC)"')
line(680,452,534,452,stroke=CYAN,sw=2,op=.95)
line(534,462,940,462,stroke=CYAN,sw=2,op=.95,dash="8 5")

# ---------- ROOM C : CDU ----------
# room label leader first, so the pipework draws over it
path("M917,204 V337",sw=1,op=.7); dot(917,339)
for cx0 in (846,910):
    rect(cx0,340,54,FLOOR_T-340,sw=1.2,op=.85)
    rect(cx0+8,350,38,40,sw=1,op=.7,fill="none")
    for k in range(7): line(cx0+10,355+k*5.5,cx0+44,355+k*5.5,stroke=GREY,sw=1,op=.8)
    rect(cx0+8,398,14,8,sw=1,op=.6,fill="none")
    line(cx0,430,cx0+54,430,stroke=GREY,sw=1,op=.7)
    circle(cx0+27,452,8,stroke=CYAN,sw=1.5,op=.95)
    path(f"M{cx0+31},447 L{cx0+22},452 L{cx0+31},457 Z",stroke=CYAN,sw=1,op=.9,fill=CYAN)   # pump, discharging toward racks
# primary loop headers (chiller <-> CDU), dropped into the empty band under the ceiling
line(866,256,1036,256,stroke=CYAN,sw=2,op=.95)                       # supply header
line(882,270,1050,270,stroke=CYAN,sw=2,op=.95,dash="8 5")            # return header
line(866,256,866,340,stroke=CYAN,sw=1.5,op=.9)                       # drop (no crossing)
path("M930,256 V267 q6,3 0,6 V340",stroke=CYAN,sw=1.5,op=.9)         # drop with jump over return header
for dx in (882,946): line(dx,270,dx,340,stroke=CYAN,sw=1.5,op=.9,dash="5 4")
path("M1036,256 V267 q6,3 0,6 V424",stroke=CYAN,sw=2,op=.95)         # supply riser, jumps return header
line(1050,270,1050,424,stroke=CYAN,sw=2,op=.95,dash="8 5")           # return riser
# expansion tank on the return riser
rect(1043,222,14,32,rx=6,sw=1.1,op=.8)
line(1050,254,1050,270,stroke=CYAN,sw=1.2,op=.9)
circle(1050,218,2,stroke=WHITE,sw=1,op=.7)
line(834,214,1000,214,stroke=GREY,sw=1,op=.55,dash="2 3")   # ceiling cable tray (secondary)

# ---------- RIGHT YARD : chiller + water storage tank ----------
rect(1020,FLOOR_T,84,8,sw=1,op=.6,fill="url(#conc)")
rect(1024,424,76,22,rx=11,sw=1.3,op=.85)
rect(1024,449,76,21,rx=10,sw=1.3,op=.85)
line(1040,446,1040,449,sw=1,op=.7); line(1084,446,1084,449,sw=1,op=.7)
rect(1064,406,32,18,sw=1.1,op=.8); circle(1080,415,5,stroke=WHITE,sw=1,op=.8)
# condenser water loop to roof units (supply arrow mid-riser, pointing up)
path("M1100,432 H1140 V300",stroke=CYAN,sw=1.5,op=.9,extra=' marker-end="url(#arrC)"')
path("M1140,300 V150 H996",stroke=CYAN,sw=1.5,op=.9)
path("M1100,442 H1152 V158 H996",stroke=CYAN,sw=1.5,op=.9,dash="6 4")
# make-up water storage tank (vertical cylinder) fed from the main
rect(1106,FLOOR_T,32,8,sw=1,op=.6,fill="url(#conc)")
rect(1109,452,26,18,sw=1.1,op=.8)
ellipse(1122,452,13,3.5,sw=1.1,op=.85,fill="panel")
circle(1122,447,1.5,stroke=WHITE,sw=1,op=.7)
line(1135,462,1166,462,stroke=CYAN,sw=1.1,op=.9)

# ---------- ROOF : cooling tower (856) + dry cooler (928) ----------
tx=856
rect(tx,118,68,ROOF_T-118,sw=1.2,op=.85)
path(f"M{tx+16},118 L{tx+20},104 H{tx+48} L{tx+52},118 Z",sw=1.1,op=.8,fill="#FFFFFF",extra=' fill-opacity="0.05"')
ellipse(tx+34,111,12,3,sw=1,op=.75)
circle(tx+34,111,1.8,stroke=WHITE,sw=1,op=.8)
for yy in (128,134,140,146): line(tx+6,yy,tx+62,yy,stroke=GREY,sw=1,op=.85)
rect(tx+2,150,64,ROOF_T-150,sw=1,op=.6,fill="none")
path(f"M{tx+4},157 q4,-3 8,0 t8,0 t8,0 t8,0 t8,0 t8,0 t8,0",stroke=CYAN,sw=1,op=.85)
# dry cooler: fan deck with three fans over a louvred finned coil
tx=928
rect(tx,136,68,ROOF_T-136,sw=1.2,op=.85)                 # plenum + coil casing
rect(tx,116,68,20,sw=1.1,op=.8)                          # fan deck
for fx in (tx+14,tx+34,tx+54):
    circle(fx,126,9,stroke=WHITE,sw=1,op=.8)
    circle(fx,126,1.8,stroke=WHITE,sw=1,op=.8)
    line(fx-7,126,fx+7,126,stroke=GREY,sw=1,op=.7); line(fx,119,fx,133,stroke=GREY,sw=1,op=.7)
rect(tx+2,146,64,19,sw=1,op=.7,fill="none")              # louvred coil
for lx in range(tx+6,tx+66,4): line(lx,147,lx,164,stroke=GREY,sw=1,op=.6)
# sleeves where the make-up main and condenser loop enter the roof unit at x=996
sleeve(992,138,8); sleeve(992,147,8,14)

# ---------- ceiling-level label inside CDU room ----------
text(917,197,"CDU冷却液分配",anchor="middle")

# ---------- sky-band room labels with leaders ----------
text(369,112,"中压开关与UPS/电池",anchor="middle"); path("M369,120 V190",sw=1,op=.7); dot(369,190)
text(472,150,"网络机房/光纤主干",anchor="middle"); path("M472,158 V190",sw=1,op=.7); dot(472,190)
text(673,118,"AI机房 · 液冷机柜/冷板歧管",anchor="middle"); path("M673,126 V190",sw=1,op=.7); dot(673,190)
text(926,84,"冷却塔/干冷器",anchor="middle")
text(1090,200,"冷水机组",anchor="middle"); path("M1090,208 V404",sw=1,op=.7); dot(1090,406)

# ---------- dimension line under building ----------
line(OUT_L,574,OUT_R,574,sw=1,op=.6)
for tx in (OUT_L,427,517,829,OUT_R):
    line(tx,569,tx,579,sw=1,op=.7); line(tx-3,577,tx+3,571,sw=1,op=.7)

# ---------- legend ----------
ly=600
def leg(x,lab,stroke,sw,dash=None):
    line(x,ly,x+36,ly,stroke=stroke,sw=sw,op=.95,dash=dash,cap="round"); text(x+44,ly+6,lab,size=17)
leg(30,"电力",GOLD,2.5)
leg(132,"冷却液供",CYAN,2)
leg(270,"冷却液回",CYAN,2,"8 5")
leg(408,"光纤",WHITE,1.4,"1.5 3.5")
leg(510,"给水",CYAN,1.1)
# scale bar
line(1040,600,1160,600,sw=1.2,op=.8)
for sx,lab in ((1040,"0"),(1100,"1"),(1160,"2 m")):
    line(sx,596,sx,604,sw=1.2,op=.8); text(sx,590,lab,size=17,anchor="middle")

add('</svg>')
svg="\n".join(out)
open('/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad/xsec_A.svg','w').write(svg)
open('/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad/xsec_final.svg','w').write(svg)
print("ok", len(svg))
