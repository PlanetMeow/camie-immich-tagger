# -*- coding: utf-8 -*-
"""
角色 / 作品中文名:character/<tag> -> zh/角色/<中文名>,copyright/<tag> -> zh/作品/<中文名>。
immich 标签筛选里直接输中文(流萤 / 原神)就能找到。

覆盖:库里出现最多的作品约 150 个(覆盖约 90% 出现次数)、角色前 300 名里有把握的(约 65%)。
中文名为起草稿(大陆通行译名),未逐个查证;发现不对直接改这里,再跑 backfill_concepts.py。
名字里不能有 "/"(immich 会当成层级),所以 Fate/stay night 写成 Fate stay night。

用法:
    from zh_names import name_tags
    name_tags(["character/firefly_(honkai:_star_rail)", "copyright/honkai:_star_rail"])
    -> ['zh/角色/流萤', 'zh/作品/崩坏：星穹铁道']
"""

COPYRIGHTS = {
    "touhou": "东方Project", "touhou_(pc-98)": "东方Project", "embodiment_of_scarlet_devil": "东方Project",
    "blue_archive": "蔚蓝档案", "kantai_collection": "舰队Collection", "arknights": "明日方舟",
    "pokemon": "宝可梦", "pokemon_swsh": "宝可梦", "pokemon_sm": "宝可梦", "pokemon_(anime)": "宝可梦",
    "genshin_impact": "原神", "vocaloid": "VOCALOID", "magical_mirai_(vocaloid)": "初音未来",
    "idolmaster": "偶像大师", "idolmaster_cinderella_girls": "偶像大师 灰姑娘女孩",
    "idolmaster_shiny_colors": "偶像大师 闪耀色彩", "idolmaster_million_live!": "偶像大师 百万现场",
    "idolmaster_(classic)": "偶像大师", "gakuen_idolmaster": "学园偶像大师",
    "honkai_(series)": "崩坏系列", "honkai_impact_3rd": "崩坏3", "honkai:_star_rail": "崩坏：星穹铁道",
    "benghuai_xueyuan": "崩坏学园",
    "fate_(series)": "Fate系列", "fate_grand_order": "Fate Grand Order", "fate_stay_night": "Fate stay night",
    "fate_extra": "Fate系列", "fate_extra_ccc": "Fate系列", "fate_kaleid_liner_prisma_illya": "魔法少女伊莉雅",
    "azur_lane": "碧蓝航线", "neon_genesis_evangelion": "新世纪福音战士", "rebuild_of_evangelion": "新世纪福音战士",
    "girls'_frontline": "少女前线", "hololive": "hololive", "hololive_english": "hololive",
    "goddess_of_victory:_nikke": "胜利女神：NIKKE", "line_(naver)": "LINE",
    "persona": "女神异闻录", "persona_5": "女神异闻录5", "persona_5_the_royal": "女神异闻录5",
    "persona_4": "女神异闻录4", "persona_3": "女神异闻录3",
    "nijisanji": "彩虹社", "nijisanji_en": "彩虹社",
    "final_fantasy": "最终幻想", "final_fantasy_xiv": "最终幻想14", "final_fantasy_vii": "最终幻想7",
    "final_fantasy_x": "最终幻想10",
    "girls_und_panzer": "少女与战车", "kirby_(series)": "星之卡比",
    "mario_(series)": "马力欧", "paper_mario": "纸片马力欧", "donkey_kong_(series)": "大金刚",
    "granblue_fantasy": "碧蓝幻想", "last_origin": "最后的起源", "wuthering_waves": "鸣潮",
    "gundam": "高达", "mobile_suit_gundam": "高达", "sousou_no_frieren": "葬送的芙莉莲",
    "overwatch": "守望先锋", "overwatch_1": "守望先锋", "umamusume": "赛马娘",
    "league_of_legends": "英雄联盟", "chainsaw_man": "电锯人", "bocchi_the_rock!": "孤独摇滚",
    "choujikuu_yousai_macross": "超时空要塞", "macross": "超时空要塞",
    "macross:_do_you_remember_love?": "超时空要塞", "macross_zero": "超时空要塞",
    "kemono_friends": "动物朋友", "love_live!": "LoveLive!", "love_live!_school_idol_project": "LoveLive!",
    "love_live!_sunshine!!": "LoveLive!", "link!_like!_love_live!": "LoveLive!",
    "zenless_zone_zero": "绝区零", "punishing:_gray_raven": "战双帕弥什", "tokyo_ghoul": "东京喰种",
    "bang_dream!": "BanG Dream!", "bang_dream!_it's_mygo!!!!!": "BanG Dream! MyGO",
    "project_moon": "Project Moon", "limbus_company": "边狱公司", "lobotomy_corporation": "脑叶公司",
    "boku_no_hero_academia": "我的英雄学院", "marvel": "漫威", "spider-man_(series)": "蜘蛛侠",
    "dc_comics": "DC漫画", "batman_(series)": "蝙蝠侠",
    "resident_evil": "生化危机", "danganronpa_(series)": "弹丸论破",
    "danganronpa_2:_goodbye_despair": "弹丸论破", "danganronpa:_trigger_happy_havoc": "弹丸论破",
    "mahou_shoujo_madoka_magica": "魔法少女小圆", "mahou_shoujo_madoka_magica_(anime)": "魔法少女小圆",
    "ace_combat": "皇牌空战", "berserk": "剑风传奇", "elden_ring": "艾尔登法环",
    "re:zero_kara_hajimeru_isekai_seikatsu": "Re：从零开始的异世界生活", "kimetsu_no_yaiba": "鬼灭之刃",
    "nier:automata": "尼尔：机械纪元", "nier_(series)": "尼尔", "metal_gear_(series)": "合金装备",
    "metal_gear_solid": "合金装备", "lycoris_recoil": "莉可丽丝", "kamitsubaki_studio": "神椿",
    "naruto_(series)": "火影忍者", "project_sekai": "世界计划", "undertale": "Undertale",
    "akebi-chan_no_serafuku": "明日酱的水手服", "dark_souls_(series)": "黑暗之魂", "dark_souls_i": "黑暗之魂",
    "dark_souls_iii": "黑暗之魂", "golden_kamuy": "黄金神威", "spy_x_family": "间谍过家家",
    "metroid": "银河战士", "bloodborne": "血源诅咒", "super_smash_bros.": "任天堂明星大乱斗",
    "darling_in_the_franxx": "DARLING in the FRANXX", "transformers": "变形金刚",
    "cyberpunk_(series)": "赛博朋克", "cyberpunk_edgerunners": "赛博朋克：边缘行者",
    "monogatari_(series)": "物语系列", "bakemonogatari": "物语系列",
    "suzumiya_haruhi_no_yuuutsu": "凉宫春日的忧郁", "animal_crossing": "动物森友会",
    "bishoujo_senshi_sailor_moon": "美少女战士", "splatoon_(series)": "斯普拉遁", "splatoon_1": "斯普拉遁",
    "among_us": "Among Us", "sono_bisque_doll_wa_koi_wo_suru": "更衣人偶坠入爱河", "star_wars": "星球大战",
    "mushoku_tensei": "无职转生", "atelier_(series)": "炼金工房", "atelier_ryza": "炼金工房",
    "hibike!_euphonium": "吹响！上低音号", "xenoblade_chronicles_(series)": "异度神剑",
    "harry_potter_(series)": "哈利·波特", "wizarding_world": "哈利·波特", "dungeon_meshi": "迷宫饭",
    "one-punch_man": "一拳超人", "onmyoji": "阴阳师", "the_legend_of_zelda": "塞尔达传说",
    "girls_band_cry": "少女乐队的呐喊", "shingeki_no_kyojin": "进击的巨人",
    "kono_subarashii_sekai_ni_shukufuku_wo!": "为美好的世界献上祝福！", "street_fighter": "街头霸王",
    "dungeon_and_fighter": "地下城与勇士", "yu-gi-oh!": "游戏王", "sen_to_chihiro_no_kamikakushi": "千与千寻",
    "alice_in_wonderland": "爱丽丝梦游仙境", "fire_emblem": "火焰纹章", "fire_emblem_heroes": "火焰纹章",
    "meitantei_conan": "名侦探柯南", "call_of_duty": "使命召唤", "sanrio": "三丽鸥",
    "jojo_no_kimyou_na_bouken": "JOJO的奇妙冒险", "princess_connect!": "公主连结", "armored_core": "装甲核心",
    "fullmetal_alchemist": "钢之炼金术师", "bleach": "死神", "reverse:1999": "重返未来：1999",
    "kill_la_kill": "斩服少女", "mahjong_soul": "雀魂", "ace_attorney": "逆转裁判", "initial_d": "头文字D",
    "guilty_gear": "罪恶装备", "inuyasha": "犬夜叉", "sonic_(series)": "索尼克", "tekken": "铁拳",
    "black_rock_shooter": "黑岩射手", "make_heroine_ga_oo_sugiru!": "败犬女主太多了！",
    "journey_to_the_west": "西游记", "assault_lily": "突击莉莉", "hyouka": "冰菓",
    "osomatsu-kun": "阿松", "osomatsu-san": "阿松", "osomatsu_(series)": "阿松",
    "cthulhu_mythos": "克苏鲁神话", "tokyo_afterschool_summoners": "东京放课后召唤师", "elsword": "艾尔之光",
}

CHARACTERS = {
    # ===== 东方Project =====
    "remilia_scarlet": "蕾米莉亚·斯卡雷特", "hakurei_reimu": "博丽灵梦", "yakumo_yukari": "八云紫",
    "kirisame_marisa": "雾雨魔理沙", "izayoi_sakuya": "十六夜咲夜", "flandre_scarlet": "芙兰朵露·斯卡雷特",
    "konpaku_youmu": "魂魄妖梦", "konpaku_youmu_(ghost)": "魂魄妖梦", "hong_meiling": "红美铃",
    "saigyouji_yuyuko": "西行寺幽幽子", "shiki_eiki": "四季映姬", "patchouli_knowledge": "帕秋莉·诺蕾姬",
    "shameimaru_aya": "射命丸文", "fujiwara_no_mokou": "藤原妹红", "hinanawi_tenshi": "比那名居天子",
    "yagokoro_eirin": "八意永琳", "inubashiri_momiji": "犬走椛", "yakumo_ran": "八云蓝", "cirno": "琪露诺",
    "alice_margatroid": "爱丽丝·玛格特洛依德", "reisen_udongein_inaba": "铃仙·优昙华院·因幡",
    "komeiji_satori": "古明地觉", "kazami_yuuka": "风见幽香", "kochiya_sanae": "东风谷早苗",
    "yasaka_kanako": "八坂神奈子", "komeiji_koishi": "古明地恋", "lunasa_prismriver": "露娜萨·普莉兹姆利巴",
    "kawashiro_nitori": "河城荷取", "chen": "橙", "mystia_lorelei": "米斯蒂娅·萝蕾拉",
    "merlin_prismriver": "梅露兰·普莉兹姆利巴", "lyrica_prismriver": "莉莉卡·普莉兹姆利巴",
    "ibuki_suika": "伊吹萃香", "morichika_rinnosuke": "森近霖之助", "onozuka_komachi": "小野塚小町",
    "maribel_hearn": "玛艾露贝莉·赫恩", "usami_renko": "宇佐见莲子", "clownpiece": "克劳恩皮丝",
    "kamishirasawa_keine": "上白泽慧音", "medicine_melancholy": "梅蒂欣·梅兰可莉", "hoshiguma_yuugi": "星熊勇仪",
    "inaba_tewi": "因幡帝", "moriya_suwako": "洩矢诹访子", "wriggle_nightbug": "莉格露·奈特巴格",
    "reiuji_utsuho": "灵乌路空", "koakuma": "小恶魔", "kaenbyou_rin": "火焰猫燐", "houraisan_kaguya": "蓬莱山辉夜",
    "hecatia_lapislazuli": "赫卡提亚·拉碧斯拉祖利", "rumia": "露米娅", "kumoi_ichirin": "云居一轮",
    "sunny_milk": "桑尼米尔克", "letty_whiterock": "蕾蒂·霍瓦特洛克", "kisume": "琪斯美",
    "hijiri_byakuren": "圣白莲", "tatara_kogasa": "多多良小伞", "himekaidou_hatate": "姬海棠果",
    "toramaru_shou": "寅丸星", "aki_minoriko": "秋穰子", "aki_shizuha": "秋静叶", "kurodani_yamame": "黑谷山女",
    "luna_child": "露娜切露德", "star_sapphire": "斯塔萨菲雅", "daiyousei": "大妖精", "mizuhashi_parsee": "水桥帕露西",
    "sekibanki": "赤蛮奇", "nagae_iku": "永江衣玖", "usami_sumireko": "宇佐见堇子",
    "sukuna_shinmyoumaru": "少名针妙丸", "unzan": "云山",

    # ===== VOCALOID / 虚拟主播 =====
    "hatsune_miku": "初音未来", "yuki_miku": "雪初音", "racing_miku": "赛车初音", "magical_mirai_miku": "初音未来",
    "usada_pekora": "兔田佩克拉", "minato_aqua": "凑阿库娅", "gawr_gura": "噶呜·古拉", "uruha_rushia": "润羽露西娅",
    "hoshimachi_suisei": "星街彗星", "nanashi_mumei": "七诗无铭", "shigure_ui_(vtuber)": "时雨羽衣",

    # ===== 蔚蓝档案 =====
    "rio_(blue_archive)": "调月莉音", "sensei_(blue_archive)": "老师（蔚蓝档案）",
    "doodle_sensei_(blue_archive)": "老师（蔚蓝档案）", "kisaki_(blue_archive)": "龙华妃咲",
    "yuuka_(blue_archive)": "早濑优香", "yuuka_(track)_(blue_archive)": "早濑优香", "plana_(blue_archive)": "普拉娜",
    "koharu_(blue_archive)": "下江小春", "mari_(blue_archive)": "伊落玛丽", "mari_(track)_(blue_archive)": "伊落玛丽",
    "toki_(blue_archive)": "飞鸟马时", "mika_(blue_archive)": "圣园未花", "arona_(blue_archive)": "阿罗娜",
    "aris_(blue_archive)": "天童爱丽丝", "kazusa_(blue_archive)": "杏山千纱", "hanako_(blue_archive)": "浦和花子",
    "kayoko_(blue_archive)": "鬼方佳代子", "shiroko_(blue_archive)": "砂狼白子",
    "shiroko_terror_(blue_archive)": "砂狼白子", "noa_(blue_archive)": "生盐诺亚", "miyu_(blue_archive)": "霞泽美游",
    "nozomi_(blue_archive)": "橘望", "hikari_(blue_archive)": "橘光", "hina_(blue_archive)": "空崎日奈",
    "asuna_(blue_archive)": "一之濑明日奈", "seia_(blue_archive)": "百合园圣娅", "yuzu_(blue_archive)": "花冈柚子",
    "miyako_(blue_archive)": "月雪宫子", "mutsuki_(blue_archive)": "浅黄睦月", "hifumi_(blue_archive)": "阿慈谷日富美",
    "tsurugi_(blue_archive)": "剑先鹤城", "azusa_(blue_archive)": "白洲梓", "hoshino_(blue_archive)": "小鸟游星野",
    "aru_(blue_archive)": "陆八魔亚瑠", "haruka_(blue_archive)": "伊草遥香", "iroha_(blue_archive)": "枣伊吕波",
    "hibiki_(cheer_squad)_(blue_archive)": "猫塚响", "kokona_(blue_archive)": "春原心奈",
    "natsu_(blue_archive)": "柚鸟夏", "peroro_(blue_archive)": "佩洛洛",

    # ===== 舰队Collection =====
    "admiral_(kancolle)": "提督", "ryuujou_(kancolle)": "龙骧", "kongou_(kancolle)": "金刚",
    "samuel_b._roberts_(kancolle)": "塞缪尔·B·罗伯茨", "iowa_(kancolle)": "衣阿华",
    "commandant_teste_(kancolle)": "指挥官泰斯特", "asakaze_(kancolle)": "朝风", "pola_(kancolle)": "波拉",
    "tashkent_(kancolle)": "塔什干", "maya_(kancolle)": "摩耶", "gambier_bay_(kancolle)": "甘比尔湾",
    "i-19_(kancolle)": "伊19", "warspite_(kancolle)": "厌战", "matsukaze_(kancolle)": "松风",
    "ayanami_(kancolle)": "绫波", "richelieu_(kancolle)": "黎塞留", "ikazuchi_(kancolle)": "雷",
    "hiei_(kancolle)": "比叡", "yamato_(kancolle)": "大和", "akebono_(kancolle)": "曙", "murakumo_(kancolle)": "丛云",
    "libeccio_(kancolle)": "西南风", "shigure_(kancolle)": "时雨", "bismarck_(kancolle)": "俾斯麦",
    "i-58_(kancolle)": "伊58", "yuudachi_(kancolle)": "夕立", "haruna_(kancolle)": "榛名", "kaga_(kancolle)": "加贺",
    "tokitsukaze_(kancolle)": "时津风", "gangut_(kancolle)": "甘古特", "houshou_(kancolle)": "凤翔",
    "i-8_(kancolle)": "伊8", "amatsukaze_(kancolle)": "天津风",

    # ===== 宝可梦 =====
    "pikachu": "皮卡丘", "steelix": "大钢蛇", "krabby": "大钳蟹", "omanyte": "菊石兽", "nidoking": "尼多王",
    "metagross": "巨金怪", "gastly": "鬼斯", "electabuzz": "电击兽", "pidgeotto": "比比鸟", "venusaur": "妙蛙花",
    "chansey": "吉利蛋", "shellder": "大舌贝", "tentacruel": "毒刺水母", "tentacool": "玛瑙水母",
    "nidorina": "尼多娜", "nidorino": "尼多力诺", "nidoran_(male)": "尼多朗", "exeggutor": "椰蛋树",
    "jirachi": "基拉祈", "seel": "小海狮", "dewgong": "白海狮", "lapras": "拉普拉斯", "beedrill": "大针蜂",
    "quagsire": "沼王", "golbat": "大嘴蝠", "wingull": "长翅鸥", "horsea": "墨海马", "muk": "臭臭泥",
    "cloyster": "刺甲贝", "spearow": "烈雀", "raikou": "雷公", "blastoise": "水箭龟", "mr._mime": "魔墙人偶",
    "doduo": "嘟嘟", "red_(pokemon)": "赤红",

    # ===== 原神 =====
    "kamisato_ayaka": "神里绫华", "keqing_(genshin_impact)": "刻晴", "raiden_shogun": "雷电将军",
    "yae_miko": "八重神子", "nilou_(genshin_impact)": "妮露", "nahida_(genshin_impact)": "纳西妲",
    "furina_(genshin_impact)": "芙宁娜", "lumine_(genshin_impact)": "荧", "barbara_(genshin_impact)": "芭芭拉",
    "ganyu_(genshin_impact)": "甘雨", "hu_tao_(genshin_impact)": "胡桃", "mona_(genshin_impact)": "莫娜",
    "shenhe_(genshin_impact)": "申鹤", "sangonomiya_kokomi": "珊瑚宫心海", "klee_(genshin_impact)": "可莉",
    "fischl_(genshin_impact)": "菲谢尔", "mavuika_(genshin_impact)": "玛薇卡", "boo_tao_(genshin_impact)": "胡桃（幽灵）",

    # ===== 崩坏系列 =====
    "kafka_(honkai:_star_rail)": "卡芙卡", "fu_xuan_(honkai:_star_rail)": "符玄",
    "silver_wolf_(honkai:_star_rail)": "银狼", "firefly_(honkai:_star_rail)": "流萤",
    "robin_(honkai:_star_rail)": "知更鸟", "huohuo_(honkai:_star_rail)": "藿藿",
    "elysia_(honkai_impact)": "爱莉希雅", "elysia_(herrscher_of_human:_ego)_(honkai_impact)": "爱莉希雅",
    "bronya_zaychik": "布洛妮娅·扎伊切克", "seele_vollerei": "希儿·芙乐艾", "kiana_kaslana": "琪亚娜·卡斯兰娜",
    "rita_rossweisse": "丽塔·洛丝薇瑟",

    # ===== 明日方舟 =====
    "suzuran_(arknights)": "铃兰", "amiya_(arknights)": "阿米娅", "doctor_(arknights)": "博士（明日方舟）",
    "exusiai_(arknights)": "能天使", "texas_(arknights)": "德克萨斯", "skadi_(arknights)": "斯卡蒂",
    "muelsyse_(arknights)": "缪尔赛思", "swire_(arknights)": "诗怀雅",

    # ===== 鸣潮 / 绝区零 =====
    "jinhsi_(wuthering_waves)": "今汐", "changli_(wuthering_waves)": "长离", "camellya_(wuthering_waves)": "椿",
    "rover_(wuthering_waves)": "漂泊者", "female_rover_(wuthering_waves)": "漂泊者",
    "shorekeeper_(wuthering_waves)": "守岸人", "hoshimi_miyabi": "星见雅",

    # ===== 碧蓝航线 / NIKKE =====
    "manjuu_(azur_lane)": "指挥喵", "commander_(azur_lane)": "指挥官（碧蓝航线）", "st._louis_(azur_lane)": "圣路易斯",
    "st._louis_(luxurious_wheels)_(azur_lane)": "圣路易斯", "sirius_(azur_lane)": "天狼星", "taihou_(azur_lane)": "大凤",
    "rapi_(nikke)": "拉毗", "alice_(nikke)": "爱丽丝（NIKKE）",

    # ===== 女神异闻录5 =====
    "amamiya_ren": "雨宫莲", "takamaki_anne": "高卷杏", "niijima_makoto": "新岛真", "okumura_haru": "奥村春",
    "sakura_futaba": "佐仓双叶", "morgana_(persona_5)": "摩尔加纳", "yoshizawa_kasumi": "芳泽霞",
    "akechi_gorou": "明智吾郎", "kitagawa_yuusuke": "喜多川祐介",

    # ===== EVA =====
    "souryuu_asuka_langley": "惣流·明日香·兰格雷", "ayanami_rei": "绫波丽", "ikari_shinji": "碇真嗣",
    "ikari_gendou": "碇源堂", "eva_01": "初号机",

    # ===== 其他 =====
    "frieren": "芙莉莲", "fern_(sousou_no_frieren)": "菲伦",
    "gotoh_hitori": "后藤一里", "kita_ikuyo": "喜多郁代", "ijichi_nijika": "伊地知虹夏", "yamada_ryo": "山田凉",
    "togawa_sakiko": "丰川祥子", "nagasaki_soyo": "长崎素世", "chihaya_anon": "千早爱音", "wakaba_mutsumi": "若叶睦",
    "fujita_kotone": "藤田琴音",
    "2b_(nier:automata)": "2B", "d.va_(overwatch)": "D.Va", "bastion_(overwatch)": "堡垒",
    "kirby": "卡比", "mario": "马力欧", "samus_aran": "萨姆斯·阿兰", "chun-li": "春丽",
    "warrior_of_light_(ff14)": "光之战士", "akebi_komichi": "明日小路", "yor_briar": "约尔",
    "artoria_pendragon_(fate)": "阿尔托莉雅·潘德拉贡", "saber_(fate)": "Saber",
    "illyasviel_von_einzbern": "伊莉雅斯菲尔·冯·爱因兹贝伦",
    "hunter_(bloodborne)": "猎人（血源诅咒）", "amamiya_kokoro": "天宫心", "inoue_takina": "井之上泷奈",
    "nishikigi_chisato": "锦木千束", "emilia_(re:zero)": "爱蜜莉雅", "rem_(re:zero)": "雷姆",
    "higuchi_madoka": "樋口圆香", "reze_(chainsaw_man)": "蕾塞", "makima_(chainsaw_man)": "玛奇玛",
    "yoru_(chainsaw_man)": "夜（电锯人）", "yumemi_riamu": "梦见莉亚梦", "kaname_madoka": "鹿目圆",
    "serval_(kemono_friends)": "薮猫", "reisalin_stout": "莱莎琳·斯托特", "kitagawa_marin": "喜多川海梦",
    "nagato_yuki": "长门有希", "tachibana_arisu": "橘爱丽丝", "agnes_tachyon_(umamusume)": "爱丽速子",
    "zaku_ii": "扎古II", "zaku": "扎古", "ghost_(modern_warfare_2)": "幽灵（使命召唤）",
    "arnold_schwarzenegger": "阿诺·施瓦辛格", "producer_(idolmaster)": "制作人（偶像大师）",
    "yanami_anna": "八奈见杏菜", "okabe_rintarou": "冈部伦太郎",
}


def name_tags(taglist):
    """已有的 character/ copyright/ 标签 -> zh/角色/<中文名>、zh/作品/<中文名>(去重保序)"""
    out = []
    for t in taglist:
        if t.startswith("character/"):
            zh = CHARACTERS.get(t[10:])
            if zh:
                out.append("zh/角色/" + zh)
        elif t.startswith("copyright/"):
            zh = COPYRIGHTS.get(t[10:])
            if zh:
                out.append("zh/作品/" + zh)
    return list(dict.fromkeys(out))


assert not any("/" in v for v in list(CHARACTERS.values()) + list(COPYRIGHTS.values()))

if __name__ == "__main__":
    print(name_tags(["character/firefly_(honkai:_star_rail)", "copyright/honkai:_star_rail", "copyright/touhou"]))
    print(f"作品 {len(COPYRIGHTS)} 条,角色 {len(CHARACTERS)} 条")
