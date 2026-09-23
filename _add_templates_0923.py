# -*- coding: utf-8 -*-
"""BSAI Qwen Prompt Enhancer - 新增模板 2026-09-23
16 pose（人物动作姿势，全球全网姿势体系）+ 12 inspiration（灵感精选：AI2Image + Prompt123 两站提取）
"""
import json, io, sys

BASE = r"C:\BSAI\ComfyUI-BSAI_pro_v41\ComfyUI\custom_nodes\BSAI_Qwen_Prompt_Enhancer"
TEMPLATES = BASE + r"\templates\templates.json"
TEXTS = BASE + r"\web\template_texts.json"

POSE_PREFIX = "你是资深人体动作与姿态指导（Pose Director）。请把用户的画面描述转写为「{CN}」的高质量英文提示词，精确控制人物姿态。\n\n姿势锚点（必须体现）：\n{ANCHOR}\n\n转换规则：保留原描述的人物外貌、服装、场景、镜头与情绪不变，仅把肢体语言重写为上述姿态；姿态必须明确可执行、无歧义，禁止含糊的“站着/坐着/躺着”。\n输出：一段完整英文提示词（含姿势关键词 {KEYS}，并描述身体重心、肢体角度与动态方向）。"

pose_templates = [
 ("pose_standing_natural", "人物动作姿势 · 自然站姿（Contrapposto 重心偏移）",
  "欧美人体姿态教科书式自然站立：重心单腿支撑、髋肩反向倾斜、松弛随性",
  POSE_PREFIX.format(CN="自然站姿", KEYS="natural standing, contrapposto, relaxed stance",
   ANCHOR="- 核心姿势关键词：natural standing pose / contrapposto（重心偏移站姿）\n- 重心：落在支撑腿（supporting leg），另一腿自然微屈放松\n- 髋部向一侧自然送出（hip shifted to one side），肩线反向倾斜（shoulders tilted opposite）\n- 手臂自然下垂或轻放体侧，头部微偏（slight head tilt），目光放松\n- 典型动作：casual stance, weight on one leg, relaxed shoulders")),
 ("pose_standing_arms", "人物动作姿势 · 手臂站姿（叉腰/抱臂/插兜/背后）",
  "四种经典上肢站姿：叉腰、抱臂、手插兜、手背后，人物气势与性格各异",
  POSE_PREFIX.format(CN="手臂站姿", KEYS="hands on hips, arms crossed, hands in pockets, hands behind back",
   ANCHOR="- 核心姿势关键词：双手叉腰 hands on hips / 抱臂 arms crossed / 手插兜 hands in pockets / 手背后 hands behind back\n- 叉腰：拇指朝后或朝前，肘部外展，肩胛微收，下巴微抬\n- 抱臂：双臂交叠于胸前，可微耸肩体现防备或自信\n- 插兜：单手或双手插入口袋，肩线放松，重心单腿\n- 手背后：挺胸收腹，站姿端正（正式/军姿感）\n- 变量：用户可选择其中一种手臂姿态")),
 ("pose_power_hero", "人物动作姿势 · 英雄力量站姿（Power Stance）",
  "超级英雄/领袖气场：双脚宽开、挺胸昂首、握拳或披风飘动，强存在感",
  POSE_PREFIX.format(CN="英雄力量站姿", KEYS="power stance, heroic pose, commanding presence",
   ANCHOR="- 核心姿势关键词：power stance / heroic pose / wide stance\n- 双脚与肩同宽或更宽（legs wide apart），脚尖微外八\n- 挺胸（chest out），肩胛后收，下颌微抬（chin up）\n- 双手握拳置于身侧（fists clenched at sides）或双手叉腰\n- 可加披风/大衣随风飘动（cape flowing in wind）、低角度仰拍强化气场\n- 典型场景：英雄登场、演讲、领袖宣言、角色立绘")),
 ("pose_sitting_chair", "人物动作姿势 · 椅子坐姿（正坐/侧坐/翘腿）",
  "椅坐体系：端正坐姿、放松靠背、翘二郎腿、反坐椅背、侧坐扶手",
  POSE_PREFIX.format(CN="椅子坐姿", KEYS="sitting on chair, legs crossed, leaning back",
   ANCHOR="- 核心姿势关键词：sitting on a chair / perched on edge / figure four sitting\n- 正坐：背脊挺直、双膝并拢或微开、手放膝上\n- 翘腿：一腿叠于另一腿膝上（leg crossed over knee），身体微后靠\n- 侧坐：身体转向扶手一侧，双腿并拢垂放\n- 反坐：面对椅背跨坐，双臂搭在椅背顶端（慵懒/掌控感）\n- 变量：椅子类型（办公椅/沙发/吧台凳/王座）、坐姿方向")),
 ("pose_sitting_floor", "人物动作姿势 · 地板坐姿（盘腿/蝴蝶坐/正座/抱膝）",
  "日系与瑜伽地板坐姿体系：盘腿、蝴蝶坐、正座（seiza）、割座（wariza）、抱膝",
  POSE_PREFIX.format(CN="地板坐姿", KEYS="cross-legged, butterfly sitting, seiza, hugging knees",
   ANCHOR="- 核心姿势关键词：cross-legged 盘腿 / butterfly sitting 蝴蝶坐 / seiza 正座 / wariza 割座 / hugging knees 抱膝\n- 盘腿：双腿交叉盘坐，脊柱挺直，手放膝上\n- 蝴蝶坐：双脚掌相对、双膝外展贴地（坐骨着地）\n- 正座：双膝跪地臀部落于脚跟上，上身挺拔（和服/茶道）\n- 割座：臀部坐于两脚之间地面（少女坐姿）\n- 抱膝：双膝收至胸前双手环抱（脆弱/蜷缩/撒娇）\n- 视角：平视或低角度近景")),
 ("pose_sitting_crossed", "人物动作姿势 · 悬坐翘腿（凳子/台阶/窗台）",
  "高处悬坐：坐在凳子/台阶/窗台边沿，双腿交叠或自然垂荡，灵动松弛",
  POSE_PREFIX.format(CN="悬坐翘腿", KEYS="perched sitting, dangling legs, ankle on knee",
   ANCHOR="- 核心姿势关键词：perched on edge / sitting on stool/step/windowsill\n- 重心：臀部位于坐面边沿，身体微前倾或后靠\n- 腿姿一：双腿交叠（legs crossed at knee）\n- 腿姿二：一脚踝搭在另一膝上（ankle on knee, figure four）\n- 腿姿三：双腿自然垂荡轻晃（dangling legs swinging）\n- 典型场景：窗台、吧台凳、天台边沿、台阶")),
 ("pose_kneel_squat", "人物动作姿势 · 跪蹲匍匐（单膝/双膝/深蹲/低蹲）",
  "跪与蹲体系：单膝下跪、双膝跪地、深蹲、低蹲警戒、匍匐",
  POSE_PREFIX.format(CN="跪蹲匍匐", KEYS="kneeling, one knee down, deep squat, crouching",
   ANCHOR="- 核心姿势关键词：kneeling 跪姿 / one knee down 单膝下跪 / deep squat 深蹲 / low crouch 低蹲 / prone crawl 匍匐\n- 单膝下跪：一膝着地一腿弓起（求婚/宣誓/行礼）\n- 双膝跪地：双膝并拢或分开，臀部可落于脚跟或直立\n- 深蹲：全脚掌着地、臀部下沉、大腿贴小腿（squat）\n- 低蹲：半蹲重心压低、手撑膝或地面（警戒/潜行）\n- 匍匐：身体贴近地面用手肘或腹部支撑（prone）")),
 ("pose_lying_recline", "人物动作姿势 · 躺卧姿势（仰/侧/俯/大字/肘撑）",
  "躺卧体系：仰卧、侧卧、俯卧、大字躺、肘撑侧躺、胎儿蜷缩",
  POSE_PREFIX.format(CN="躺卧姿势", KEYS="lying on back/side/stomach, reclining, fetal position",
   ANCHOR="- 核心姿势关键词：lying on back 仰卧 / lying on side 侧卧 / lying on stomach 俯卧 / starfish 大字躺 / fetal position 胎儿蜷缩\n- 仰卧：背贴地面/床面，可双手交叠于腹或脑后\n- 侧卧：单臂撑头（elbow prop）或手臂自然前伸，双腿微曲\n- 俯卧：趴伏，可单手托腮或双臂前伸\n- 大字躺：四肢完全舒展（放松/解脱感）\n- 胎儿蜷缩：双膝收至胸前双手环抱（脆弱感）\n- 场景：床/草地/沙滩/地板，视角可俯拍或平视")),
 ("pose_walk_run", "人物动作姿势 · 走跑位移（行走/大步/冲刺/慢跑/踮脚）",
  "运动位移体系：行走、大步流星、冲刺跑、慢跑、踮脚潜行、正步",
  POSE_PREFIX.format(CN="走跑位移", KEYS="walking, striding, sprinting, jogging, tiptoeing",
   ANCHOR="- 核心姿势关键词：walking 行走 / striding 大步 / sprinting 冲刺跑 / jogging 慢跑 / tiptoeing 踮脚 / marching 正步\n- 行走：一腿前迈一腿后蹬，手臂自然摆动，重心移动\n- 大步：跨幅大、躯干前倾、有动势（stride）\n- 冲刺：身体前倾约45度、屈臂高摆、腿部交替腾空（sprint）\n- 踮脚：脚掌着地、身体微前倾（潜行/悄悄靠近）\n- 可加运动模糊/地面反光强化速度感")),
 ("pose_jump_leap", "人物动作姿势 · 跳跃腾空（起跳/飞跃/腾空/坠落）",
  "跳跃体系：原地起跳、飞跃、单脚跳、扑跃、腾空滞停、坠落",
  POSE_PREFIX.format(CN="跳跃腾空", KEYS="jumping, leaping, hopping, midair, falling",
   ANCHOR="- 核心姿势关键词：jump 起跳 / leap 飞跃 / hop 单脚跳 / pounce 扑跃 / midair 腾空滞停 / falling 坠落\n- 起跳：双腿屈膝蹬地、手臂上摆、脚尖离地瞬间\n- 飞跃：身体伸展呈对角线（leap，舞者/跑酷）\n- 腾空滞停：身体完全离地、四肢展开、衣摆发丝上飘（慢镜感）\n- 坠落：身体下坠、四肢张开或蜷缩、表情紧张\n- 视角：低角度仰拍强化腾空高度")),
 ("pose_combat_fight", "人物动作姿势 · 战斗格斗（拳/腿/持械/防御/落地）",
  "武打体系：格斗架势、出拳、踢腿、高踢、持械、防御、超级英雄落地",
  POSE_PREFIX.format(CN="战斗格斗", KEYS="fighting stance, punch, kick, high kick, sword stance, superhero landing",
   ANCHOR="- 核心姿势关键词：fighting stance 格斗架势 / punch 出拳 / kick 踢腿 / high kick 高踢 / defensive guard 防御 / sword stance 持剑 / aiming 瞄准 / superhero landing 超级英雄落地\n- 格斗架势：双脚前后分立、双拳护于面前、重心下沉（boxer stance）\n- 出拳：前手直拳、转腰送肩、后脚蹬地（dynamic punch）\n- 高踢：单腿高抬过头（high kick，侧踢/回旋踢）\n- 持械：双手或单手执剑/刀/枪，架势明确\n- 超级英雄落地：单膝跪地一手撑地、一手后扬、尘土飞溅\n- 变量：徒手/持械、进攻/防守")),
 ("pose_hand_gesture", "人物动作姿势 · 手部手势（比心/耶/挥手/指点/祈祷/握拳）",
  "手势体系：比心、剪刀手、挥手、指点、祈祷合十、握拳、竖起拇指、打响指",
  POSE_PREFIX.format(CN="手部手势", KEYS="peace sign, thumbs up, pointing, waving, praying, flexing, shaka",
   ANCHOR="- 核心姿势关键词：peace sign 剪刀手 / thumbs up 竖拇指 / pointing 指点 / waving 挥手 / praying 合十祈祷 / flexing 秀肌肉 / shaka 摇滚手势 / blowing kiss 飞吻\n- 手部特写优先：手势为主角时建议近景或特写镜头\n- 配合表情：手势情绪与面部表情一致（喜悦/自信/俏皮/虔诚）\n- 单/双手皆可，必要时结合上半身动态")),
 ("pose_emotion_perform", "人物动作姿势 · 情绪演绎（胜利/哭泣/受惊/思考/欢呼）",
  "情感姿态体系：胜利振臂、掩面哭泣、受惊退缩、耸肩无奈、托腮思考、欢呼雀跃、鞠躬",
  POSE_PREFIX.format(CN="情绪演绎", KEYS="victory pose, crying, scared, shrugging, thinking, cheering, bowing",
   ANCHOR="- 核心姿势关键词：victory 胜利振臂 / crying 掩面哭泣 / scared 受惊退缩 / shrugging 耸肩 / thinking 托腮思考 / cheering 欢呼 / bowing 鞠躬\n- 胜利：双臂上举握拳、仰头、身体舒展（arms raised in triumph）\n- 哭泣：双手掩面或拭泪、肩膀微颤、低头\n- 受惊：身体后仰、双手捂嘴或抱头、瞳孔放大\n- 思考：单手托腮、目光斜上、另一手环胸\n- 情绪必须具象化为肢体细节（禁止抽象“很悲伤”等）")),
 ("pose_dance_sport", "人物动作姿势 · 舞蹈体育（芭蕾/瑜伽/健美/滑板/街舞）",
  "专业动作体系：芭蕾阿拉贝斯克、瑜伽体式、健美展示、滑板、街舞定格、体操",
  POSE_PREFIX.format(CN="舞蹈体育", KEYS="arabesque, yoga pose, bodybuilder flex, skateboard, dance freeze",
   ANCHOR="- 核心姿势关键词：ballet arabesque 芭蕾阿拉贝斯克 / yoga pose 瑜伽体式（如 tree pose, warrior pose）/ bodybuilder flex 健美展示 / skateboard trick 滑板动作 / dance freeze 街舞定格\n- 芭蕾：单腿支撑、后腿高抬、双臂舒展（arabesque）\n- 瑜伽：体式标准、呼吸感、衣料随动作贴合\n- 健美：双肱二头肌展示（double biceps）、肌肉充血线条\n- 滑板：ollie/空中抓板/滑行压弯等瞬间\n- 定格动态：衣摆、发丝、汗珠的瞬时状态")),
 ("pose_motion_capture", "人物动作姿势 · 动态瞬间（回眸/转身/甩发/迎风）",
  "抓拍感动态：行走回眸、甩发、回头、转身、迎风前倾、半途停顿",
  POSE_PREFIX.format(CN="动态瞬间", KEYS="looking back over shoulder, hair flip, mid-turn, leaning into wind",
   ANCHOR="- 核心姿势关键词：looking back over shoulder 回眸 / hair flip 甩发 / mid-turn 转身瞬间 / leaning into wind 迎风前倾\n- 回眸：身体前向、头部回转、视线看镜头或侧方（肩后回望）\n- 甩发：头发呈弧形飞起、颈部发力、表情自信\n- 转身：裙摆/衣摆旋动、重心随转体偏移（twirl）\n- 迎风：身体前倾约30度、衣发向后飘、单手压帽或拢发\n- 强调动势线（motion lines）与衣料物理飘动")),
 ("pose_two_person", "人物动作姿势 · 双人互动（拥抱/牵手/背靠背/对峙）",
  "双人关系姿态：拥抱、牵手、背靠背、面对面、公主抱、共舞、扶持",
  POSE_PREFIX.format(CN="双人互动", KEYS="hugging, holding hands, back to back, facing each other, carrying",
   ANCHOR="- 核心姿势关键词：hugging 拥抱 / holding hands 牵手 / back to back 背靠背 / facing each other 对视 / carrying（princess carry）公主抱 / dancing together 共舞\n- 拥抱：双臂环抱对方、身体贴合、可闭眼或微笑\n- 牵手：十指相扣或掌心相握、手臂自然下垂或举起\n- 背靠背：两人背部相倚、同向或反向站立（羁绊感）\n- 对峙：面对面、距离张力、手势或武器对峙\n- 注意两人身高差、肢体接触点与视线关系")),
]

insp_templates = [
 ("inspiration_myth_poster", "灵感精选 · 东方神话人物志百科海报（AI2Image #415）",
  "提取自 AI2Image GPT Image 2 #415：以东方神话人物为中心的中文信息图海报模板",
  "你是东方神话视觉设定师、古籍图谱设计师和中文信息图设计师。请基于人物名称在东方神话、民间传说、古籍中的已知形象，生成一张竖版 A4「东方神话人物志」百科海报，内容完整、视觉统一、具有东方神话气质。\n\n布局（从上到下）：\n1. 顶部：人物名称大标题（烫金书法体）+ 副题（称号，如“齐天大圣”）\n2. 中央主视觉：人物全身立像（传统服饰 + 标志法器，工笔重彩风格）\n3. 中部信息区：称号 / 出身 / 主要事迹 / 法器四张信息卡（中文小字 + 小图标）\n4. 底部：传统图腾纹样装饰带（祥云/水纹/回纹）\n\n风格锚点：古籍手卷质感、米黄宣纸底色、工笔重彩 + 烫金线框、水墨晕染点缀。\n变量：PERSON = 人物名（如“孙悟空”“哪吒”“嫦娥”）；若用户未指定，默认“孙悟空”。\n输出：一段完整中文提示词（可直接用于千问文生图）。"),
 ("inspiration_travel_poster", "灵感精选 · 中世纪城市旅行海报（AI2Image #418）",
  "提取自 AI2Image GPT Image 2 #418：复古旅游海报，严格三色系 + Art-Deco 排版",
  "你是复古海报设计师。请把用户的城市信息转写为一张中世纪风格竖版旅行海报的高质量英文提示词。\n\n模板结构：\nCreate a vertical mid-century travel poster for {CITY} featuring {LANDMARK}. Use a strict 3-color palette: cream paper base, {COLOR1}, {COLOR2}. Flat retro illustration style with {CITY} skyline silhouette, {LANDMARK} as the central focus, art-deco typography reading \"{TITLE}\", distressed paper texture, classic travel-bureau border frame. Vintage 1950s tourism aesthetic, warm nostalgic mood.\n\n变量：\n- CITY: 城市名（如 PARIS）\n- LANDMARK: 地标（如 EIFFEL TOWER）\n- COLOR1 / COLOR2: 主色（如 burnt orange / deep teal）\n- TITLE: 海报标题文字（英文双引号内）\n输出：填入变量后的完整英文提示词。"),
 ("inspiration_morning_photo", "灵感精选 · 室内晨间写实摄影（AI2Image #414）",
  "提取自 AI2Image GPT Image 2 #414：日常纪实摄影质感，自然光 + 真实生活感",
  "你是写实生活摄影师。请把用户描述转写为一张「室内晨间写实摄影」的高质量英文提示词。\n\n模板结构：\nA close-medium shot of {SUBJECT} in {ROOM} on an ordinary morning, captured in authentic daily-life photography style: natural window light from the left, soft diffused shadows, candid unposed moment, subtle film grain, shallow depth of field, warm color palette, hyper-detailed textures, realistic natural skin texture, no makeup look, documentary intimacy, calm morning atmosphere.\n\n变量：\n- SUBJECT: 人物描述（如 a young woman with messy hair in a beige sweater）\n- ROOM: 房间（如 a sunlit bedroom / a cozy kitchen）\n输出：填入变量后的完整英文提示词。"),
 ("inspiration_landmark_poster", "灵感精选 · 极简建筑地标海报（AI2Image #411）",
  "提取自 AI2Image GPT Image 2 #411：奢华极简主义 + 建筑几何抽象",
  "你是极简主义平面设计师。请把用户指定的建筑地标转写为一张奢华极简海报的高质量英文提示词。\n\n模板结构：\nDesign a luxury minimalist poster centered on a famous architectural landmark {LANDMARK}. The focal composition: geometric abstraction of {LANDMARK} silhouette, thin elegant lines, single accent color {COLOR} on an ivory background, generous negative space, small uppercase title \"{TITLE}\" at the bottom, subtle architectural grid guides, premium editorial print aesthetic, refined typography.\n\n变量：\n- LANDMARK: 地标（如 the Eiffel Tower / a pagoda）\n- COLOR: 点缀色（如 matte gold / deep navy）\n- TITLE: 标题（英文大写，如 \"PARIS\"）\n输出：填入变量后的完整英文提示词。"),
 ("inspiration_jp_illust", "灵感精选 · 日系手绘涂鸦半身插画（AI2Image #423）",
  "提取自 AI2Image GPT Image 2 #423：日式插画 + 手绘涂鸦线条",
  "你是日系插画师。请把用户的角色描述转写为一张「日系手绘涂鸦半身插画」的高质量英文提示词。\n\n模板结构：\nGenerate an illustration of {SUBJECT} as you imagine it. Features include a Japanese illustration style, distinct character design, hand-drawn graffito lineart with loose energetic ink strokes, limited color palette of {COLORS}, half-body composition, playful rough texture, cel-like shading with visible sketch lines, subtle background doodles, expressive eyes, clean confident outlines.\n\n变量：\n- SUBJECT: 角色描述（如 a girl with twin tails wearing a school uniform）\n- COLORS: 配色（如 pink, mint, and cream）\n输出：填入变量后的完整英文提示词。"),
 ("inspiration_study_photo", "灵感精选 · Cozy Academia 学习手记（AI2Image #408）",
  "提取自 AI2Image GPT Image 2 #408：电影感学习美学，金色暖光",
  "你是电影感纪实摄影师。请把用户描述转写为一张「Cozy Academia 学习手记」风格照片的高质量英文提示词。\n\n模板结构：\nDreamy cinematic study aesthetic: {SUBJECT} studying {ACTIVITY} at {PLACE} during golden hour. Warm backlight streaming through leaves, dust motes floating in sunbeams, books and {PROPS} scattered naturally, cozy academia mood, film photography look, medium shot with soft bokeh, muted warm tones, nostalgic intimate atmosphere, hyper-detailed textures.\n\n变量：\n- SUBJECT: 人物（如 a young Asian girl with long dark hair）\n- ACTIVITY: 活动（如 reading a novel / writing notes）\n- PLACE: 地点（如 at a wooden table outdoors）\n- PROPS: 道具（如 a steaming coffee cup, vintage stationery）\n输出：填入变量后的完整英文提示词。"),
 ("inspiration_brand_ad", "灵感精选 · 品牌广告信息图海报（Prompt123 image #1223）",
  "提取自 Prompt123 图片站 Nano Banana #1223：品牌户外广告 + blob 模块化信息图系统",
  "你是资深品牌形象设计师与 CGI 广告美术指导。请把用户提供的品牌信息转写为一张「品牌户外广告信息图海报」的高质量英文提示词。\n\n模板结构（四阶段）：\n1. 场景环境：城市人行道上斜靠建筑墙面的 citylight 广告牌（约120×175cm），粗野主义混凝土墙面 + 树叶斑驳投影\n2. 海报系统：海报底色取自品牌主色系的浅色调；网格内分布 7-9 个几何有机 blob 单元——实心色块（品牌深色）/ 材质摄影块（品牌相关材质微距）/ 描边轮廓块（品牌强调色）\n3. 产品窗口：核心产品置于一个 blob 窗口内（如为饮品、汽车局部、单鞋、科技产品等，裁切进 blob 形状，占内部 70-85%）\n4. 排版与光线：左下角 4-8 词品牌标语 + 右下角品牌字标，其余零文字；右上 45 度自然主光，4:5 竖版，50mm 镜头\n\n负面约束：产品不漂浮于网格之上、无独立投影、无白底、画面除标语与字标外不出现任何文字。\n变量：BRAND = 品牌名/品类（如 coffee brand / luxury watch brand）。\n输出：一段完整英文提示词。"),
 ("inspiration_anime_city", "灵感精选 · 动漫城市故事数字海报（Prompt123 image #975）",
  "提取自 Prompt123 图片站 #975：GTA V 漫画网格 + 多城市“Side Stories”系列海报",
  "你是动漫海报设计师。请把用户指定的城市转写为一张「动漫城市故事数字海报」（GTA V 风格漫画网格）的高质量提示词，使用 JSON 结构化输出。\n\n模板结构：\nAnime-style digital poster, GTA V-inspired comic grid, cinematic anime tone, nostalgic warmth mixed with urban energy. Use this JSON structure:\n{ \"title\": \"{CITY} Side Stories – Volume 1\", \"art_style\": \"...\", \"center_panel\": \"...\", \"surrounding_panels\": [6 个分镜短句], \"palette\": [3 个主色] }\n\n规则：\n- center_panel：一位角色在城市标志性背景下（如 {LANDMARK}）\n- surrounding_panels：6 个城市生活瞬间（街头咖啡/夜景/雨天/通勤等）\n- palette：3 个能代表该城市的配色\n变量：CITY、LANDMARK、中心角色描述。\n输出：一段含完整 JSON 的英文提示词。"),
 ("inspiration_ghibli", "灵感精选 · 吉卜力手绘风格（Prompt123 image 风格栏目）",
  "源自 Prompt123 图片站「吉卜力」风格栏目：宫崎骏式手绘动画美学",
  "你是资深风格转换师。请把用户的画面描述转写为「吉卜力手绘风格」（Studio Ghibli-inspired hand-drawn animation）的高质量英文提示词。\n\n风格锚点：\n- 画面：水彩晕染背景（soft watercolor backgrounds），细腻手绘线条（delicate hand-drawn lines）\n- 光影：柔和自然光、云影分层、空气感与微风（gentle light, layered clouds, breezy atmosphere）\n- 色彩：温暖淡雅的自然色系（cream, moss green, sky blue, sunset gold）\n- 场景：田园村落、奇幻森林、天空之城式悬浮世界、蒸汽小镇\n- 质感：手绘动画赛璐璐 + 水彩纸纹，无照片噪点，氛围治愈怀旧\n\n转换规则：保留原描述的人物、动作、场景、构图不变，仅将视觉语言转换为吉卜力手绘动画风格。\n输出：一段完整英文提示词（含风格词 Ghibli-inspired, hand-drawn anime, soft watercolor backgrounds）。"),
 ("inspiration_ink", "灵感精选 · 水墨工笔风格（Prompt123 image 风格栏目）",
  "源自 Prompt123 图片站「水墨工笔」风格栏目：东方水墨 + 工笔重彩融合",
  "你是资深风格转换师。请把用户的画面描述转写为「水墨工笔风格」（Chinese ink wash + gongbi fine brush）的高质量英文提示词。\n\n风格锚点：\n- 基底：宣纸纹理（xuan paper texture），米白底色，可留大片空白\n- 墨色：浓淡干湿五色墨（ink wash gradation），笔触可见\n- 线条：工笔细线勾边（fine gongbi outlines），精准流畅\n- 设色：可淡彩晕染（subtle mineral pigments：石青/赭石/花青）或纯水墨\n- 题材：山水、花鸟、人物、建筑均可；画面可有书法落款（calligraphy seal）\n- 意境：留白、虚实、气韵生动\n\n转换规则：保留原描述内容，仅将视觉语言转换为水墨工笔风格。\n输出：一段完整英文提示词（含风格词 Chinese ink wash painting, gongbi fine brush style, xuan paper）。"),
 ("inspiration_minimal", "灵感精选 · 极简版式风格（Prompt123 image 风格栏目）",
  "源自 Prompt123 图片站「极简版式」风格栏目：瑞士式网格 + 大留白",
  "你是资深风格转换师。请把用户的画面/文案描述转写为「极简版式风格」（Swiss minimal layout）的高质量英文提示词。\n\n风格锚点：\n- 版式：网格对齐（modular grid），大留白（generous white space），元素居左/居中排列\n- 配色：单色或双色系（black + one accent color），克制\n- 字体：无衬线大字号标题（bold sans-serif），层级分明，字数极少\n- 图形：几何图形（圆形/方形/线条）作点缀，无多余装饰\n- 适用：海报、封面、信息图、品牌视觉\n\n转换规则：保留原描述的文案与信息层级，仅将视觉语言转换为极简版式。\n输出：一段完整英文提示词（含风格词 Swiss minimal design, modular grid, generous white space）。"),
 ("inspiration_watercolor", "灵感精选 · 水彩手绘风格（Prompt123 image 风格栏目）",
  "源自 Prompt123 图片站「水彩手绘」风格栏目：透明水彩 + 纸纹",
  "你是资深风格转换师。请把用户的画面描述转写为「水彩手绘风格」（watercolor illustration）的高质量英文提示词。\n\n风格锚点：\n- 质感：透明水彩晕染（transparent watercolor washes），颜色自然渗透叠加\n- 纸纹：水彩纸颗粒可见（cold-press paper texture），边缘柔和\n- 线条：可有淡墨铅稿线（light pencil underdrawing）或无线稿纯色块\n- 色彩：清新淡雅（soft pastel palette），留白透气\n- 题材：风景、花卉、人物、小动物、生活场景\n\n转换规则：保留原描述内容，仅将视觉语言转换为水彩手绘风格。\n输出：一段完整英文提示词（含风格词 watercolor illustration, transparent washes, paper texture）。"),
]

def main():
    with io.open(TEMPLATES, "r", encoding="utf-8") as f:
        data = json.load(f)
    tpls = data["templates"]
    existing = {t["id"] for t in tpls}
    added = []
    for t in pose_templates + insp_templates:
        if t[0] in existing:
            print("SKIP existing:", t[0]); continue
        tpls.append({"id": t[0], "name": t[1], "desc": t[2], "text": t[3], "type": t[1].startswith("人物动作姿势") and "pose" or "inspiration"})
        added.append(t[0])
    data["meta"]["updated"] = "2026-09-23"
    with io.open(TEMPLATES, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("templates.json updated: +%d (total %d)" % (len(added), len(tpls)))

    with io.open(TEXTS, "r", encoding="utf-8") as f:
        tdata = json.load(f)
    tlist = tdata["templates"]
    texisting = {t["id"] for t in tlist}
    tadded = 0
    for t in pose_templates + insp_templates:
        if t[0] in texisting:
            continue
        tlist.append({"id": t[0], "name": t[1], "type": t[1].startswith("人物动作姿势") and "pose" or "inspiration", "text": t[3]})
        tadded += 1
    with io.open(TEXTS, "w", encoding="utf-8") as f:
        json.dump(tdata, f, ensure_ascii=False, indent=1)
    print("template_texts.json updated: +%d (total %d)" % (tadded, len(tlist)))

if __name__ == "__main__":
    main()
