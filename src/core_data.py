# core_data.py

NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty", "Bold", "Docile", "Relaxed",
    "Impish", "Lax", "Timid", "Hasty", "Serious", "Jolly", "Naive", "Modest",
    "Mild", "Quiet", "Bashful", "Rash", "Calm", "Gentle", "Sassy", "Careful", "Quirky"
]

STAT_MOD_NAMES = ["Atk", "Def", "Spe", "SpA", "SpD"]

SUBSTRUCT_ORDER = [
    (0,1,2,3), (0,1,3,2), (0,2,1,3), (0,3,1,2), (0,2,3,1), (0,3,2,1),
    (1,0,2,3), (1,0,3,2), (2,0,1,3), (3,0,1,2), (2,0,3,1), (3,0,2,1),
    (1,2,0,3), (1,3,0,2), (2,1,0,3), (3,1,0,2), (2,3,0,1), (3,2,0,1),
    (1,2,3,0), (1,3,2,0), (2,1,3,0), (3,1,2,0), (2,3,1,0), (3,2,1,0)
]

HOENN_INTERNAL_TO_NAT = {
    277:252, 278:253, 279:254, 280:255, 281:256, 282:257, 283:258, 284:259, 285:260,
    286:261, 287:262, 288:263, 289:264, 290:265, 291:266, 292:267, 293:268, 294:269,
    295:270, 296:271, 297:272, 298:273, 299:274, 300:275, 301:290, 302:291, 303:292,
    304:276, 305:277, 306:285, 307:286, 308:327, 309:278, 310:279, 311:283, 312:284,
    313:320, 314:321, 315:300, 316:301, 317:352, 318:343, 319:344, 320:299, 321:324,
    322:302, 323:339, 324:340, 325:370, 326:341, 327:342, 328:349, 329:350, 330:318,
    331:319, 332:328, 333:329, 334:330, 335:296, 336:297, 337:309, 338:310, 339:322,
    340:323, 341:363, 342:364, 343:365, 344:331, 345:332, 346:361, 347:362, 348:337,
    349:338, 350:298, 351:325, 352:326, 353:311, 354:312, 355:303, 356:307, 357:308,
    358:333, 359:334, 360:360, 361:355, 362:356, 363:315, 364:287, 365:288, 366:289,
    367:316, 368:317, 369:357, 370:293, 371:294, 372:295, 373:366, 374:367, 375:368,
    376:359, 377:353, 378:354, 379:336, 380:335, 381:369, 382:304, 383:305, 384:306,
    385:351, 386:313, 387:314, 388:345, 389:346, 390:347, 391:348, 392:280, 393:281,
    394:282, 395:371, 396:372, 397:373, 398:374, 399:375, 400:376, 401:377, 402:378,
    403:379, 404:382, 405:383, 406:384, 407:380, 408:381, 409:385, 410:386, 411:358
}

GEN3_ITEMS = {
    1: ("Master Ball", "master-ball"), 2: ("Ultra Ball", "ultra-ball"),
    3: ("Great Ball", "great-ball"), 4: ("Poké Ball", "poke-ball"),
    5: ("Safari Ball", "safari-ball"), 6: ("Net Ball", "net-ball"),
    7: ("Dive Ball", "dive-ball"), 8: ("Nest Ball", "nest-ball"),
    9: ("Repeat Ball", "repeat-ball"), 10: ("Timer Ball", "timer-ball"),
    11: ("Luxury Ball", "luxury-ball"), 12: ("Premier Ball", "premier-ball"),
    13: ("Potion", "potion"), 19: ("Full Restore", "full-restore"),
    20: ("Max Potion", "max-potion"), 21: ("Hyper Potion", "hyper-potion"),
    22: ("Super Potion", "super-potion"), 23: ("Full Heal", "full-heal"),
    24: ("Revive", "revive"), 25: ("Max Revive", "max-revive"),
    26: ("Fresh Water", "fresh-water"), 27: ("Soda Pop", "soda-pop"),
    28: ("Lemonade", "lemonade"), 29: ("Moomoo Milk", "moomoo-milk"),
    34: ("Ether", "ether"), 35: ("Max Ether", "max-ether"),
    36: ("Elixir", "elixir"), 37: ("Max Elixir", "max-elixir"),
    44: ("Berry Juice", "berry-juice"), 45: ("Sacred Ash", "sacred-ash"),
    63: ("HP Up", "hp-up"), 64: ("Protein", "protein"), 65: ("Iron", "iron"),
    66: ("Carbos", "carbos"), 67: ("Calcium", "calcium"),
    68: ("Rare Candy", "rare-candy"), 69: ("PP Up", "pp-up"),
    70: ("Zinc", "zinc"), 71: ("PP Max", "pp-max"),
    93: ("Sun Stone", "sun-stone"), 94: ("Moon Stone", "moon-stone"),
    95: ("Fire Stone", "fire-stone"), 96: ("Thunderstone", "thunder-stone"),
    97: ("Water Stone", "water-stone"), 98: ("Leaf Stone", "leaf-stone"),
    110: ("Nugget", "nugget"), 111: ("Heart Scale", "heart-scale"),
    133: ("Cheri Berry", "cheri-berry"), 134: ("Chesto Berry", "chesto-berry"),
    135: ("Pecha Berry", "pecha-berry"), 136: ("Rawst Berry", "rawst-berry"),
    138: ("Leppa Berry", "leppa-berry"), 139: ("Oran Berry", "oran-berry"),
    141: ("Lum Berry", "lum-berry"), 142: ("Sitrus Berry", "sitrus-berry"),
    168: ("Liechi Berry", "liechi-berry"), 169: ("Ganlon Berry", "ganlon-berry"),
    170: ("Salac Berry", "salac-berry"), 171: ("Petaya Berry", "petaya-berry"),
    179: ("BrightPowder", "bright-powder"), 180: ("White Herb", "white-herb"),
    181: ("Macho Brace", "macho-brace"), 182: ("Exp. Share", "exp-share"),
    183: ("Quick Claw", "quick-claw"), 184: ("Soothe Bell", "soothe-bell"),
    185: ("Mental Herb", "mental-herb"), 186: ("Choice Band", "choice-band"),
    187: ("King's Rock", "kings-rock"), 188: ("SilverPowder", "silver-powder"),
    189: ("Amulet Coin", "amulet-coin"), 191: ("Soul Dew", "soul-dew"),
    192: ("DeepSeaTooth", "deep-sea-tooth"), 193: ("DeepSeaScale", "deep-sea-scale"),
    194: ("Smoke Ball", "smoke-ball"), 195: ("Everstone", "everstone"),
    196: ("Focus Band", "focus-band"), 197: ("Lucky Egg", "lucky-egg"),
    198: ("Scope Lens", "scope-lens"), 199: ("Metal Coat", "metal-coat"),
    200: ("Leftovers", "leftovers"), 201: ("Dragon Scale", "dragon-scale"),
    202: ("Light Ball", "light-ball"), 203: ("Soft Sand", "soft-sand"),
    204: ("Hard Stone", "hard-stone"), 205: ("Miracle Seed", "miracle-seed"),
    206: ("BlackGlasses", "black-glasses"), 207: ("Black Belt", "black-belt"),
    208: ("Magnet", "magnet"), 209: ("Mystic Water", "mystic-water"),
    210: ("Sharp Beak", "sharp-beak"), 211: ("Poison Barb", "poison-barb"),
    212: ("NeverMeltIce", "never-melt-ice"), 213: ("Spell Tag", "spell-tag"),
    214: ("TwistedSpoon", "twisted-spoon"), 215: ("Charcoal", "charcoal"),
    216: ("Dragon Fang", "dragon-fang"), 217: ("Silk Scarf", "silk-scarf"),
    218: ("Up-Grade", "up-grade"), 219: ("Shell Bell", "shell-bell"),
    224: ("Thick Club", "thick-club"), 225: ("Stick", "stick"),
}
for _tm in range(1, 51):
    GEN3_ITEMS[288 + _tm] = (f"TM{_tm:02d}", "tm-normal")

def get_item_info(item_id: int) -> tuple[str, str]:
    if item_id == 0:
        return ("None", "")
    return GEN3_ITEMS.get(item_id, (f"Item #{item_id}", "poke-ball"))
