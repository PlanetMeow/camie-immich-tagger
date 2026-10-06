# -*- coding: utf-8 -*-
"""
中文概念标签:把多个 Danbooru general 标签归到一个中文概念下,写成层级标签 zh/<大类>/<概念>,
例如 pantyhose / thighhighs / black_pantyhose ... -> zh/服饰/丝袜;from_below -> zh/视角/仰视。
immich 的标签页会出现「服饰 / 视角 / 表情 / 姿势 ...」目录,点进去就是全部相关图。

与 tag_translations.py(一对一平铺翻译 zh/长发)互不冲突,两者并存。
成员写法:精确标签名;"re:<正则>"(fullmatch)批量匹配颜色/款式变体;"-<标签>" 从该概念里排除。
正则统一不匹配 no_ 开头的标签(no_bra / no_halo 是"没有",不能归进内衣/光环)。
概念名里不能有 "/"(会被 immich 当成层级)。

用法:
    from concept_tags import concept_tags
    concept_tags(["black_pantyhose", "from_below", "smile"])
    -> ['zh/服饰/丝袜', 'zh/服饰/黑丝', 'zh/服饰/连裤袜', 'zh/视角/仰视', 'zh/表情/微笑']
"""
import re
from functools import lru_cache

CONCEPTS = {
    # ===== 视角 / 构图 =====
    "视角/仰视": ["from_below"],
    "视角/俯视": ["from_above"],
    "视角/背影": ["from_behind", "facing_away", "back"],
    "视角/侧面": ["from_side", "profile"],
    "视角/回眸": ["looking_back"],
    "视角/看向镜头": ["looking_at_viewer", "facing_viewer"],
    "视角/特写": ["close-up", "portrait", "face"],
    "视角/上半身": ["upper_body", "cowboy_shot"],
    "视角/全身": ["full_body"],
    "视角/下半身": ["lower_body", "head_out_of_frame", "feet_out_of_frame"],
    "视角/远景": ["wide_shot", "scenery", "landscape"],
    "视角/倾斜构图": ["dutch_angle"],
    "视角/第一人称": ["pov", "pov_hands"],
    "视角/透视": ["foreshortening"],
    "视角/自拍": ["selfie"],
    "视角/多视图": ["multiple_views", "reference_sheet", "expressions"],
    "视角/景深虚化": ["depth_of_field", "blurry_background", "blurry_foreground"],

    # ===== 表情 =====
    "表情/微笑": ["smile", "grin", ":d", "happy", "^_^", ":3", "light_smile", "smug"],
    "表情/大笑": [":d", "laughing", "open_mouth_smile"],
    "表情/张嘴": ["open_mouth", ":o"],
    "表情/脸红": ["blush", "nose_blush", "blush_stickers", "full-face_blush"],
    "表情/害羞": ["embarrassed", "shy", "flustered"],
    "表情/哭": ["crying", "tears", "streaming_tears", "crying_with_eyes_open", "teardrop"],
    "表情/伤心": ["sad", "crying", "tears"],
    "表情/闭眼": ["closed_eyes", "^_^"],
    "表情/眨眼": ["one_eye_closed", "wink"],
    "表情/半眯眼": ["half-closed_eyes", "narrowed_eyes"],
    "表情/无表情": ["expressionless", "blank_stare", "empty_eyes"],
    "表情/皱眉": ["frown", "v-shaped_eyebrows", "furrowed_brow"],
    "表情/生气": ["angry", "annoyed", "clenched_teeth"],
    "表情/惊讶": ["surprised", ":o", "wide-eyed", "shocked"],
    "表情/害怕": ["scared", "nervous", "trembling"],
    "表情/吐舌": ["tongue_out", "tongue", ":p", ";p"],
    "表情/流汗": ["sweatdrop", "flying_sweatdrops", "nervous_sweating"],
    "表情/得意": ["smug", "grin", "smirk"],
    "表情/喘气": ["heavy_breathing", "breath", "panting"],
    "表情/嘟嘴": ["pout"],

    # ===== 姿势 / 动作 =====
    "姿势/站": ["standing", "standing_on_one_leg", "contrapposto"],
    "姿势/坐": ["sitting", "wariza", "seiza", "crossed_legs", "indian_style", "sitting_on_floor",
               "on_chair", "on_couch", "butterfly_sitting"],
    "姿势/跷二郎腿": ["crossed_legs"],
    "姿势/躺": ["lying", "on_back", "on_side", "on_stomach"],
    "姿势/趴": ["on_stomach", "all_fours"],
    "姿势/跪": ["kneeling", "all_fours", "seiza"],
    "姿势/蹲": ["squatting"],
    "姿势/弯腰前倾": ["leaning_forward", "bent_over"],
    "姿势/抬手": ["arm_up", "arms_up", "hand_up", "hands_up"],
    "姿势/伸手": ["outstretched_arm", "outstretched_arms", "reaching", "reaching_towards_viewer"],
    "姿势/叉腰": ["hand_on_own_hip", "hands_on_own_hips"],
    "姿势/比耶": ["v", "double_v"],
    "姿势/抬腿": ["leg_up", "legs_up", "knee_up", "knees_up", "standing_on_one_leg"],
    "姿势/分腿": ["spread_legs"],
    "姿势/背手": ["arms_behind_back"],
    "姿势/拥抱": ["hug", "hugging_own_legs", "hugging_object"],
    "姿势/走": ["walking"],
    "姿势/跑": ["running"],
    "姿势/飞行漂浮": ["flying", "floating", "jumping", "midair"],
    "姿势/睡觉": ["sleeping"],
    "姿势/歪头": ["head_tilt"],
    "姿势/托腮": ["head_rest", "chin_rest", "hand_on_own_cheek", "hand_on_own_face"],
    "姿势/手插口袋": ["hand_in_pocket", "hands_in_pockets"],
    "姿势/撑手": ["arm_support"],
    "姿势/手放胸前": ["hand_on_own_chest"],
    "姿势/伸懒腰": ["stretching"],
    "姿势/战斗": ["battle", "fighting_stance", "fighting"],

    # ===== 服饰 =====
    "服饰/丝袜": ["pantyhose", "thighhighs", "re:.+_pantyhose", "re:.+_thighhighs", "zettai_ryouiki",
                "single_thighhigh", "thighband_pantyhose", "legwear", "re:.+_legwear", "fishnets",
                "fishnet_pantyhose", "fishnet_thighhighs"],
    "服饰/黑丝": ["black_pantyhose", "black_thighhighs", "black_legwear"],
    "服饰/白丝": ["white_pantyhose", "white_thighhighs", "white_legwear"],
    "服饰/肉丝": ["brown_pantyhose", "brown_thighhighs", "brown_legwear"],
    "服饰/连裤袜": ["pantyhose", "re:.+_pantyhose", "thighband_pantyhose"],
    "服饰/过膝袜": ["thighhighs", "re:.+_thighhighs", "zettai_ryouiki", "single_thighhigh"],
    "服饰/网袜": ["fishnets", "fishnet_pantyhose", "fishnet_thighhighs", "fishnet_legwear"],
    "服饰/袜子": ["socks", "re:.+_socks", "kneehighs", "re:.+_kneehighs", "loose_socks"],
    "服饰/吊带袜": ["garter_straps", "garter_belt"],
    "服饰/裙子": ["skirt", "re:.+_skirt", "miniskirt"],
    "服饰/短裙": ["miniskirt", "short_dress", "pleated_skirt"],
    "服饰/连衣裙": ["dress", "re:.+_dress"],
    "服饰/校服": ["school_uniform", "serafuku", "sailor_collar", "re:.+_sailor_collar",
                "school_bag", "neckerchief"],
    "服饰/水手服": ["serafuku", "sailor_collar", "re:.+_sailor_collar"],
    "服饰/女仆装": ["maid", "maid_headdress", "maid_apron", "enmaided", "frilled_apron"],
    "服饰/泳装": ["swimsuit", "bikini", "re:.+_bikini", "one-piece_swimsuit", "school_swimsuit",
                "competition_swimsuit", "side-tie_bikini_bottom", "string_bikini"],
    "服饰/和服": ["kimono", "re:.+_kimono", "japanese_clothes", "obi", "yukata", "hakama"],
    "服饰/旗袍": ["china_dress"],
    "服饰/中式服装": ["china_dress", "chinese_clothes", "hanfu"],
    "服饰/兔女郎": ["playboy_bunny"],
    "服饰/紧身衣": ["leotard", "re:.+_leotard", "bodysuit", "re:.+_bodysuit", "pilot_suit", "skin_tight"],
    "服饰/内衣": ["underwear", "bra", "re:.+_bra", "panties", "re:.+_panties", "lingerie", "underwear_only",
                "camisole"],
    "服饰/外套": ["jacket", "re:.+_jacket", "coat", "re:.+_coat", "hoodie", "cardigan", "blazer", "vest"],
    "服饰/毛衣": ["sweater", "re:.+_sweater", "turtleneck", "turtleneck_sweater", "ribbed_sweater"],
    "服饰/衬衫": ["shirt", "re:.+_shirt", "collared_shirt", "dress_shirt", "t-shirt"],
    "服饰/西装正装": ["suit", "formal", "necktie", "re:.+_necktie", "office_lady"],
    "服饰/制服": ["uniform", "military_uniform", "police_uniform", "nurse"],
    "服饰/盔甲": ["armor", "re:.+_armor", "helmet", "power_armor"],
    "服饰/短裤": ["shorts", "re:.+_shorts", "short_shorts", "denim_shorts"],
    "服饰/裤子": ["pants", "re:.+_pants", "jeans"],
    "服饰/露肩": ["bare_shoulders", "off_shoulder", "strapless", "strapless_dress", "off-shoulder_dress"],
    "服饰/露脐": ["midriff", "crop_top", "stomach", "navel"],
    "服饰/透视": ["see-through", "see-through_clothes", "wet_clothes", "wet_shirt"],
    "服饰/无袖": ["sleeveless", "sleeveless_dress", "sleeveless_shirt", "tank_top"],
    "服饰/长袖": ["long_sleeves", "wide_sleeves", "sleeves_past_wrists", "sleeves_past_fingers",
                "puffy_long_sleeves", "juliet_sleeves"],
    "服饰/眼镜": ["glasses", "re:.+-framed_eyewear", "round_eyewear", "semi-rimless_eyewear", "sunglasses"],
    "服饰/帽子": ["hat", "re:.+_hat", "beret", "mob_cap", "peaked_cap", "baseball_cap", "re:.+_headwear"],
    "服饰/手套": ["gloves", "re:.+_gloves"],
    "服饰/靴子": ["boots", "re:.+_boots"],
    "服饰/高跟鞋": ["high_heels", "high_heel_boots", "stiletto_heels"],
    "服饰/鞋": ["shoes", "re:.+_footwear", "sneakers", "loafers", "sandals", "mary_janes"],
    "服饰/赤脚": ["barefoot", "no_shoes", "soles", "toes"],
    "服饰/项圈": ["choker", "re:.+_choker", "collar"],
    "服饰/发饰": ["hair_ornament", "hairclip", "hair_flower", "hair_bow", "hair_ribbon", "hairband",
                "re:.+_hairband", "x_hair_ornament", "scrunchie", "hair_bobbles", "tiara", "crown"],
    "服饰/蝴蝶结": ["bow", "re:.+_bow", "bowtie", "re:.+_bowtie", "hair_bow"],
    "服饰/首饰": ["jewelry", "earrings", "necklace", "bracelet", "ring", "piercing", "ear_piercing"],
    "服饰/耳机": ["headphones", "headset"],
    "服饰/面具口罩": ["mask", "mouth_mask", "face_mask"],
    "服饰/披风": ["cape", "capelet", "cloak"],
    "服饰/围巾": ["scarf"],
    "服饰/围裙": ["apron", "re:.+_apron"],
    "服饰/魔女": ["witch_hat", "witch"],
    "服饰/婚纱": ["wedding_dress", "bridal_veil"],
    "服饰/便服": ["casual", "t-shirt", "hoodie", "jeans"],

    # ===== 发型 =====
    "发型/长发": ["long_hair", "very_long_hair", "absurdly_long_hair"],
    "发型/短发": ["short_hair", "bob_cut", "pixie_cut"],
    "发型/中长发": ["medium_hair"],
    "发型/双马尾": ["twintails", "low_twintails", "short_twintails"],
    "发型/马尾": ["ponytail", "high_ponytail", "side_ponytail", "low_ponytail"],
    "发型/辫子": ["braid", "re:.+_braid", "re:.+_braids", "braided_ponytail", "french_braid"],
    "发型/丸子头": ["hair_bun", "double_bun", "single_hair_bun"],
    "发型/呆毛": ["ahoge"],
    "发型/刘海": ["bangs", "re:.+_bangs", "hair_between_eyes"],
    "发型/卷发": ["wavy_hair", "drill_hair", "curly_hair", "twin_drills"],
    "发型/遮眼发": ["hair_over_one_eye", "hair_over_eyes"],
    "发型/侧扎": ["two_side_up", "one_side_up"],

    # ===== 发色(下方循环补全)=====
    "发色/挑染多色": ["multicolored_hair", "two-tone_hair", "gradient_hair", "streaked_hair",
                   "colored_inner_hair", "split-color_hair"],

    # ===== 身体特征 =====
    "身体特征/兽耳": ["animal_ears", "cat_ears", "fox_ears", "wolf_ears", "rabbit_ears", "dog_ears",
                   "animal_ear_fluff", "fake_animal_ears", "extra_ears", "horse_ears", "mouse_ears"],
    "身体特征/猫耳": ["cat_ears", "cat_girl"],
    "身体特征/狐耳": ["fox_ears", "fox_girl"],
    "身体特征/兔耳": ["rabbit_ears", "rabbit_girl"],
    "身体特征/尾巴": ["tail", "re:.+_tail"],
    "身体特征/翅膀": ["wings", "re:.+_wings"],
    "身体特征/角": ["horns", "re:.+_horns"],
    "身体特征/光环": ["halo", "re:.+_halo"],
    "身体特征/精灵耳": ["pointy_ears", "elf"],
    "身体特征/虎牙": ["fang", "fangs", "skin_fang"],
    "身体特征/痣": ["mole", "re:mole_.+"],
    "身体特征/雀斑": ["freckles"],
    "身体特征/纹身": ["tattoo", "re:.+_tattoo"],
    "身体特征/深肤色": ["dark_skin", "dark-skinned_female", "dark-skinned_male", "tan", "tanlines"],
    "身体特征/异色瞳": ["heterochromia"],
    "身体特征/发光眼": ["glowing_eyes", "glowing_eye"],
    "身体特征/肌肉": ["muscular", "muscular_female", "muscular_male", "abs"],
    "身体特征/巨乳": ["large_breasts", "huge_breasts", "gigantic_breasts"],
    "身体特征/贫乳": ["small_breasts", "flat_chest"],
    "身体特征/大腿": ["thighs", "thick_thighs", "thigh_gap", "skindentation"],
    "身体特征/腿": ["legs", "bare_legs", "kneepits"],
    "身体特征/足": ["feet", "soles", "toes", "foot_focus", "toenails"],
    "身体特征/美甲": ["nail_polish", "re:.+_nails"],
    "身体特征/机械义体": ["mechanical_arms", "prosthesis", "android", "cyborg", "joints", "robot_joints"],
    "身体特征/湿身": ["wet", "wet_clothes", "wet_hair", "wet_shirt", "wet_panties", "wet_swimsuit"],

    # ===== 人物 =====
    "人物/单人": ["solo", "solo_focus"],
    "人物/双人": ["2girls", "2boys", "couple"],
    "人物/多人": ["multiple_girls", "multiple_boys", "3girls", "4girls", "5girls", "6+girls", "3boys",
                "6+boys", "group_picture"],
    "人物/男性": ["1boy", "2boys", "multiple_boys", "male_focus"],
    "人物/女性": ["1girl", "2girls", "multiple_girls"],
    "人物/百合": ["yuri"],
    "人物/无人物": ["no_humans"],
    "人物/兽人": ["furry", "furry_female", "furry_male", "animalization"],
    "人物/机器人": ["robot", "android"],
    "人物/虚拟主播": ["virtual_youtuber"],

    # ===== 场景 =====
    "场景/室内": ["indoors"],
    "场景/室外": ["outdoors"],
    "场景/卧室床上": ["bed", "bedroom", "on_bed", "bed_sheet", "pillow"],
    "场景/教室学校": ["classroom", "school", "chalkboard", "school_desk"],
    "场景/海边": ["beach", "ocean", "shore", "waves"],
    "场景/水": ["water", "underwater", "pool", "partially_submerged", "bathing", "bath", "onsen"],
    "场景/天空": ["sky", "blue_sky", "cloud", "cloudy_sky"],
    "场景/白天": ["day", "sunlight", "light_rays"],
    "场景/夜晚": ["night", "night_sky", "star_(sky)", "starry_sky", "moon", "full_moon"],
    "场景/夕阳": ["sunset", "evening", "twilight", "orange_sky"],
    "场景/雨": ["rain"],
    "场景/雪": ["snow", "snowing", "winter"],
    "场景/城市": ["city", "cityscape", "street", "building", "skyscraper", "road", "city_lights", "rooftop"],
    "场景/自然": ["nature", "forest", "tree", "grass", "mountain", "field", "flower_field", "river", "rock"],
    "场景/花": ["flower", "re:.+_flower", "rose", "petals", "cherry_blossoms", "bouquet",
              "-hair_flower", "-hat_flower"],
    "场景/废墟": ["ruins", "destruction"],
    "场景/咖啡厅餐厅": ["cafe", "restaurant"],
    "场景/神社和风": ["shrine", "torii", "japanese_architecture"],
    "场景/简单背景": ["simple_background", "white_background", "grey_background", "black_background",
                   "gradient_background", "transparent_background",
                   "re:(blue|red|pink|yellow|purple|green|orange|brown)_background"],
    "场景/科幻": ["science_fiction", "cyberpunk", "space", "spacecraft", "hologram"],
    "场景/奇幻": ["fantasy", "magic", "magic_circle"],

    # ===== 画风 / 类型 =====
    "画风/漫画": ["comic", "4koma", "speech_bubble", "manga"],
    "画风/黑白": ["monochrome", "greyscale", "spot_color"],
    "画风/草稿线稿": ["sketch", "lineart", "unfinished"],
    "画风/像素": ["pixel_art"],
    "画风/3D": ["3d", "blender_(medium)"],
    "画风/写实": ["realistic", "photorealistic"],
    "画风/Q版": ["chibi", "super_deformed"],
    "画风/立绘设定": ["tachi-e", "reference_sheet", "character_sheet", "concept_art"],
    "画风/截图聊天": ["fake_screenshot", "fake_phone_screenshot", "chat_log", "user_interface", "screenshot"],
    "画风/游戏画面": ["gameplay_mechanics", "health_bar", "heads-up_display", "minimap"],
    "画风/表情包": ["meme", "reaction_image"],
    "画风/恐怖": ["horror_(theme)"],

    # ===== 道具 / 持物 =====
    "道具/武器": ["weapon", "holding_weapon", "sword", "katana", "gun", "rifle", "handgun", "knife", "spear",
                "polearm", "staff", "shield", "bow_(weapon)", "dagger", "axe", "scythe",
                "holding_sword", "holding_gun", "holding_staff", "holding_polearm", "holding_knife"],
    "道具/刀剑": ["sword", "katana", "holding_sword", "knife", "dagger", "sheath"],
    "道具/枪": ["gun", "rifle", "handgun", "holding_gun", "assault_rifle", "submachine_gun", "shotgun"],
    "道具/手机": ["phone", "cellphone", "smartphone", "holding_phone"],
    "道具/书": ["book", "open_book", "holding_book"],
    "道具/食物": ["food", "fruit", "holding_food", "eating", "cake", "candy", "drinking"],
    "道具/伞": ["umbrella", "parasol"],
    "道具/乐器": ["instrument", "guitar", "piano", "microphone", "music"],
    "道具/玩偶": ["stuffed_toy", "stuffed_animal", "teddy_bear"],

    # ===== 动物 =====
    "动物/猫": ["cat"],
    "动物/狗": ["dog"],
    "动物/鸟": ["bird"],
    "动物/鱼": ["fish"],
    "动物/宝可梦": ["pokemon_(creature)"],

    # ===== 载具 =====
    "载具/汽车": ["car", "motor_vehicle", "sports_car"],
    "载具/飞机": ["aircraft", "airplane", "fighter_jet", "jet", "helicopter"],
    "载具/军用": ["military_vehicle", "tank"],
    "载具/船": ["watercraft", "ship", "boat"],
    "载具/机甲": ["mecha", "cockpit"],
}

_HAIR = {"black": "黑发", "blonde": "金发", "brown": "棕发", "light_brown": "棕发", "blue": "蓝发",
         "light_blue": "蓝发", "grey": "灰发", "white": "白发", "pink": "粉发", "purple": "紫发",
         "red": "红发", "green": "绿发", "orange": "橙发", "aqua": "青发", "silver": "灰发"}
for _en, _zh in _HAIR.items():
    CONCEPTS.setdefault("发色/" + _zh, []).append(f"{_en}_hair")

_EYES = {"black": "黑瞳", "blue": "蓝瞳", "red": "红瞳", "brown": "棕瞳", "purple": "紫瞳", "yellow": "黄瞳",
         "green": "绿瞳", "grey": "灰瞳", "pink": "粉瞳", "aqua": "青瞳", "orange": "橙瞳",
         "light_blue": "蓝瞳", "golden": "黄瞳"}
for _en, _zh in _EYES.items():
    CONCEPTS.setdefault("瞳色/" + _zh, []).append(f"{_en}_eyes")

_EXACT = {}
_REGEX = []
_EXCLUDE = {}
for _path, _members in CONCEPTS.items():
    assert _path.count("/") == 1, _path
    for _m in _members:
        if _m.startswith("re:"):
            _REGEX.append((re.compile(_m[3:]), _path))
        elif _m.startswith("-"):
            _EXCLUDE.setdefault(_path, set()).add(_m[1:])
        else:
            _EXACT.setdefault(_m, []).append(_path)


@lru_cache(maxsize=None)
def concepts_of(tag):
    """单个 general 标签 -> 它属于的概念路径(tuple)"""
    out = [p for p in _EXACT.get(tag, []) if tag not in _EXCLUDE.get(p, ())]
    if not tag.startswith("no_"):
        for rx, path in _REGEX:
            if rx.fullmatch(tag) and path not in out and tag not in _EXCLUDE.get(path, ()):
                out.append(path)
    return tuple(out)


def concept_tags(general_tags):
    """一组 general 标签(不带 general/ 前缀)-> ['zh/<大类>/<概念>', ...](去重,保持顺序)"""
    seen, out = set(), []
    for t in general_tags:
        for p in concepts_of(t):
            if p not in seen:
                seen.add(p)
                out.append("zh/" + p)
    return out


if __name__ == "__main__":
    print(concept_tags(["black_pantyhose", "from_below", "smile", "sitting", "blue_hair", "red_eyes"]))
    print(f"{len(CONCEPTS)} 个概念,{len(_EXACT)} 个精确标签,{len(_REGEX)} 条正则")
