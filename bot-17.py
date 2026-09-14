import logging
import os
import sqlite3
import random
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, ConversationHandler,
    MessageHandler, CallbackQueryHandler, PreCheckoutQueryHandler,
    ContextTypes, filters,
)
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.path.join(os.path.dirname(__file__), "music90s.db")

PREMIUM_STARS = 100  # цена Premium в Telegram Stars

# ─── Жанры 90-х ───────────────────────────────────────────────────────────────

GENRES = {
    "eurodance": {
        "name": "Eurodance 🕺",
        "desc": "Haddaway, Snap!, La Bouche, 2 Unlimited",
        "query": "eurodance 90s",
        "artists": ["Haddaway", "Snap", "La Bouche", "2 Unlimited", "Ace of Base", "Corona", "Real McCoy"],
        "color": "🟡",
        "history": (
            "🟡 *Eurodance — танцевальная революция 90-х*\n\n"
            "Eurodance родился в Германии и Швеции в начале 90-х. "
            "Синтезаторы, бит 140 BPM и незабываемые мелодии захватили весь мир.\n\n"
            "Каждые выходные в клубах Европы звучали эти треки — "
            "и люди танцевали до утра 🕺💃"
        ),
        "albums": [
            ("2 Unlimited", "No Limits!", "https://music.youtube.com/search?q=2+Unlimited+No+Limits+album"),
            ("Ace of Base", "The Sign", "https://music.youtube.com/search?q=Ace+of+Base+The+Sign+album"),
            ("La Bouche", "Sweet Dreams", "https://music.youtube.com/search?q=La+Bouche+Sweet+Dreams+album"),
            ("Corona", "The Rhythm of the Night", "https://music.youtube.com/search?q=Corona+Rhythm+Night+album"),
        ],
    },
    "russian_rock": {
        "name": "Русский рок 90-х 🎸",
        "desc": "Кино, Nautilus Pompilius, Агата Кристи, ДДТ",
        "query": "русский рок 90е",
        "artists": ["Кино", "Nautilus Pompilius", "Агата Кристи", "ДДТ", "Сплин", "Земфира", "Би-2"],
        "color": "🔴",
        "history": (
            "🔴 *Русский рок 90-х — голос эпохи*\n\n"
            "После распада СССР русский рок стал голосом целого поколения. "
            "Виктор Цой, Юрий Шевчук, Вячеслав Бутусов пели о свободе, "
            "боли и надежде.\n\n"
            "Это была музыка перемен — честная, сырая и настоящая 🎸"
        ),
        "albums": [
            ("Кино", "Чёрный альбом", "https://music.youtube.com/search?q=Кино+Черный+альбом"),
            ("Nautilus Pompilius", "Яблокитай", "https://music.youtube.com/search?q=Nautilus+Pompilius+Яблокитай"),
            ("Агата Кристи", "Опиум", "https://music.youtube.com/search?q=Агата+Кристи+Опиум"),
            ("ДДТ", "Это всё", "https://music.youtube.com/search?q=ДДТ+Это+все+альбом"),
        ],
    },
    "rnb": {
        "name": "R&B 90-х 🎤",
        "desc": "TLC, Destiny's Child, Boyz II Men, Mariah Carey",
        "query": "rnb 90s hits",
        "artists": ["TLC", "Boyz II Men", "Mariah Carey", "Whitney Houston", "SWV", "En Vogue"],
        "color": "🟣",
        "history": (
            "🟣 *R&B 90-х — душа десятилетия*\n\n"
            "R&B в 90-х переживал золотой век. TLC, Boyz II Men, Mariah Carey "
            "и Whitney Houston создавали музыку которая трогала душу.\n\n"
            "Мягкие биты, мощные голоса и истории о любви — "
            "именно так звучали 90-е для миллионов людей 🎤"
        ),
        "albums": [
            ("TLC", "CrazySexyCool", "https://music.youtube.com/search?q=TLC+CrazySexyCool+album"),
            ("Boyz II Men", "II", "https://music.youtube.com/search?q=Boyz+II+Men+II+album"),
            ("Mariah Carey", "Daydream", "https://music.youtube.com/search?q=Mariah+Carey+Daydream+album"),
            ("Whitney Houston", "The Bodyguard", "https://music.youtube.com/search?q=Whitney+Houston+Bodyguard+album"),
        ],
    },
    "grunge": {
        "name": "Гранж / Альтернатива 🤘",
        "desc": "Nirvana, Pearl Jam, Soundgarden, Alice in Chains",
        "query": "grunge alternative 90s",
        "artists": ["Nirvana", "Pearl Jam", "Soundgarden", "Alice in Chains", "Stone Temple Pilots", "Bush"],
        "color": "⚫",
        "history": (
            "⚫ *Гранж — революция из Сиэтла*\n\n"
            "В 1991 году Nirvana выпустила Nevermind и перевернула мир музыки. "
            "Гранж убил эпоху глэм-метала за одну ночь.\n\n"
            "Курт Кобейн, Эдди Веддер, Крис Корнелл — "
            "они пели о боли, отчуждении и поиске себя. "
            "Эта музыка изменила поколение навсегда 🤘"
        ),
        "albums": [
            ("Nirvana", "Nevermind", "https://music.youtube.com/search?q=Nirvana+Nevermind+album"),
            ("Pearl Jam", "Ten", "https://music.youtube.com/search?q=Pearl+Jam+Ten+album"),
            ("Soundgarden", "Superunknown", "https://music.youtube.com/search?q=Soundgarden+Superunknown+album"),
            ("Alice in Chains", "Dirt", "https://music.youtube.com/search?q=Alice+in+Chains+Dirt+album"),
        ],
    },
    "britpop": {
        "name": "Брит-поп 🇬🇧",
        "desc": "Oasis, Blur, Pulp, Suede",
        "query": "britpop 90s",
        "artists": ["Oasis", "Blur", "Pulp", "Suede", "Elastica", "Supergrass", "Travis"],
        "color": "🔵",
        "history": (
            "🔵 *Брит-поп — британское вторжение 90-х*\n\n"
            "В середине 90-х Британия ответила на американский гранж "
            "своим движением — брит-попом.\n\n"
            "Война Oasis vs Blur стала культурным событием эпохи. "
            "Обе группы выпустили синглы в один день в 1995 — "
            "и вся Британия разделилась на два лагеря 🇬🇧"
        ),
        "albums": [
            ("Oasis", "(What's the Story) Morning Glory?", "https://music.youtube.com/search?q=Oasis+Morning+Glory+album"),
            ("Blur", "Parklife", "https://music.youtube.com/search?q=Blur+Parklife+album"),
            ("Pulp", "Different Class", "https://music.youtube.com/search?q=Pulp+Different+Class+album"),
            ("Suede", "Coming Up", "https://music.youtube.com/search?q=Suede+Coming+Up+album"),
        ],
    },
    "pop": {
        "name": "Поп 90-х ✨",
        "desc": "Spice Girls, Backstreet Boys, *NSYNC, Britney",
        "query": "pop hits 90s",
        "artists": ["Spice Girls", "Backstreet Boys", "NSync", "Britney Spears", "Christina Aguilera", "Robbie Williams"],
        "color": "🟠",
        "history": (
            "🟠 *Поп 90-х — эпоха бой-бэндов и girl power*\n\n"
            "Spice Girls провозгласили Girl Power и покорили мир. "
            "Backstreet Boys и NSYNC устроили войну бой-бэндов.\n\n"
            "Britney Spears, Christina Aguilera, Robbie Williams — "
            "эти имена знал каждый ребёнок планеты. "
            "Поп 90-х был яркий, беззаботный и бесконечно заразительный ✨"
        ),
        "albums": [
            ("Spice Girls", "Spice", "https://music.youtube.com/search?q=Spice+Girls+Spice+album"),
            ("Backstreet Boys", "Millennium", "https://music.youtube.com/search?q=Backstreet+Boys+Millennium+album"),
            ("Britney Spears", "...Baby One More Time", "https://music.youtube.com/search?q=Britney+Spears+Baby+One+More+Time+album"),
            ("Robbie Williams", "Life Thru a Lens", "https://music.youtube.com/search?q=Robbie+Williams+Life+Thru+Lens+album"),
        ],
    },
}

# ─── Тематические плейлисты ───────────────────────────────────────────────────

THEMED_PLAYLISTS = {
    "party": {
        "name": "🎉 Вечеринка в стиле 90-х",
        "artists": [
            "Haddaway What Is Love", "Snap The Power", "2 Unlimited No Limit",
            "Ace of Base The Sign", "Spice Girls Wannabe", "Backstreet Boys Everybody",
            "Corona Rhythm of the Night", "La Bouche Be My Lover", "Real McCoy Another Night",
            "Ricky Martin Livin La Vida Loca", "Aqua Barbie Girl", "Vengaboys We Like to Party",
            "Whigfield Saturday Night", "Culture Beat Mr Vain", "Technotronic Pump Up the Jam",
            "Robin S Show Me Love", "Los Del Rio Macarena", "Scatman John Scatman",
            "Ini Kamoze Here Comes the Hotstepper", "Rozalla Everybody's Free",
        ],
    },
    "car": {
        "name": "🚗 Музыка для машины",
        "artists": [
            "Oasis Wonderwall", "Blur Song 2", "Nirvana Come As You Are",
            "Pearl Jam Black", "TLC Waterfalls", "Robbie Williams Angels",
            "Red Hot Chili Peppers Under the Bridge", "Foo Fighters Everlong",
            "Green Day Good Riddance", "The Offspring Come Out and Play",
            "R.E.M. Losing My Religion", "U2 One", "Alanis Morissette Ironic",
            "Sheryl Crow All I Wanna Do", "No Doubt Don't Speak",
            "Garbage Stupid Girl", "Beck Loser", "Smashing Pumpkins 1979",
            "Bush Glycerine", "Live Lightning Crashes",
        ],
    },
    "romance": {
        "name": "💕 Романтика 90-х",
        "artists": [
            "Boyz II Men End of the Road", "Mariah Carey Always Be My Baby",
            "Whitney Houston I Will Always Love You", "Celine Dion My Heart Will Go On",
            "Bryan Adams Everything I Do", "All-4-One I Swear",
            "Savage Garden Truly Madly Deeply", "Michael Bolton When A Man Loves A Woman",
            "Richard Marx Right Here Waiting", "Seal Kiss from a Rose",
            "Sade No Ordinary Love", "Des'ree You Gotta Be",
            "Toni Braxton Un-Break My Heart", "Brandy Have You Ever",
            "Monica The First Night", "En Vogue Don't Let Go",
            "SWV Right Here", "Lisa Loeb Stay",
            "Jewel You Were Meant For Me", "k.d. lang Constant Craving",
        ],
    },
    "movies": {
        "name": "🎬 Саундтреки фильмов 90-х",
        "artists": [
            "Bryan Adams Everything I Do Robin Hood", "Celine Dion My Heart Will Go On Titanic",
            "Will Smith Men in Black", "Coolio Gangsta Paradise Dangerous Minds",
            "Seal Kiss from a Rose Batman Forever", "Whitney Houston I Will Always Love You Bodyguard",
            "Elton John Can You Feel the Love Tonight Lion King",
            "Phil Collins You'll Be in My Heart Tarzan",
            "Madonna Take a Bow", "Roxette It Must Have Been Love Pretty Woman",
            "Enigma Return to Innocence", "Enya Only Time",
            "Tina Turner GoldenEye James Bond", "R. Kelly I Believe I Can Fly Space Jam",
            "Boyz II Men End of the Road Boomerang", "Puff Daddy I'll Be Missing You",
            "Janet Jackson Again Poetic Justice", "Sting Fields of Gold",
            "Ace of Base Beautiful Life", "Haddaway What Is Love Night at the Roxbury",
        ],
    },
    "workout": {
        "name": "💪 Тренировка в стиле 90-х",
        "artists": [
            "2 Unlimited Get Ready for This", "Snap Rhythm Is a Dancer",
            "La Bouche Be My Lover", "Corona Rhythm of the Night",
            "Real McCoy Another Night", "Haddaway What Is Love",
            "Technotronic Pump Up the Jam", "C+C Music Factory Gonna Make You Sweat",
            "Rozalla Everybody's Free", "Cappella U Got 2 Know",
            "Livin Joy Dreamer", "Reel 2 Real I Like to Move It",
            "MC Hammer U Can't Touch This", "Vanilla Ice Ice Ice Baby",
            "Tag Team Whoomp There It Is", "Robin S Show Me Love",
            "Culture Beat Mr Vain", "Scatman John Scatman",
            "Los Del Rio Macarena", "Vengaboys Boom Boom Boom",
        ],
    },
    "nostalgia": {
        "name": "🕰️ Чистая ностальгия",
        "artists": [
            "Кино Группа крови", "Nautilus Pompilius Крылья",
            "Агата Кристи Как на войне", "Nirvana Smells Like Teen Spirit",
            "Oasis Wonderwall", "TLC No Scrubs",
            "ДДТ Что такое осень", "Земфира Хочешь",
            "Мумий Тролль Владивосток 2000", "Backstreet Boys I Want It That Way",
            "Spice Girls Say You'll Be There", "a-ha Take On Me",
            "Roxette The Look", "Pet Shop Boys Go West",
            "Depeche Mode Personal Jesus", "The Cranberries Zombie",
            "Ace of Base All That She Wants", "Savage Garden I Want You",
            "Cher Believe", "Boyzone No Matter What",
        ],
    },
}

# ─── Настроения ───────────────────────────────────────────────────────────────

MOODS = {
    "happy": {
        "name": "😄 Радостное",
        "tracks": ["Spice Girls Wannabe", "Aqua Barbie Girl", "Ricky Martin Livin La Vida Loca",
                   "Los Del Rio Macarena", "Vengaboys We Like to Party", "Haddaway What Is Love"],
    },
    "sad": {
        "name": "😢 Грустное",
        "tracks": ["Boyz II Men End of the Road", "Celine Dion My Heart Will Go On",
                   "Whitney Houston I Will Always Love You", "Toni Braxton Un-Break My Heart",
                   "Richard Marx Right Here Waiting", "Bryan Adams Everything I Do"],
    },
    "energetic": {
        "name": "💪 Энергичное",
        "tracks": ["2 Unlimited Get Ready for This", "Snap Rhythm Is a Dancer",
                   "C+C Music Factory Gonna Make You Sweat", "Technotronic Pump Up the Jam",
                   "MC Hammer U Can't Touch This", "Reel 2 Real I Like to Move It"],
    },
    "romantic": {
        "name": "💕 Романтичное",
        "tracks": ["Savage Garden Truly Madly Deeply", "Seal Kiss from a Rose",
                   "All-4-One I Swear", "Boyz II Men I'll Make Love to You",
                   "Mariah Carey Always Be My Baby", "Des'ree You Gotta Be"],
    },
    "nostalgic": {
        "name": "🕰️ Ностальгия",
        "tracks": ["Кино Группа крови", "Nautilus Pompilius Крылья",
                   "Nirvana Come As You Are", "Oasis Wonderwall",
                   "The Cranberries Zombie", "Roxette The Look"],
    },
    "chill": {
        "name": "😌 Спокойное",
        "tracks": ["Enigma Return to Innocence", "Enya Only Time",
                   "Sade No Ordinary Love", "Massive Attack Teardrop",
                   "Portishead Glory Box", "Bjork Human Behaviour"],
    },
}

# ─── Хиты по годам с прямыми ссылками ───────────────────────────────────────

YEAR_HITS = {
    1984: [
        ("Michael Jackson", "Thriller", "https://music.youtube.com/search?q=Michael+Jackson+Thriller"),
        ("Prince", "When Doves Cry", "https://music.youtube.com/search?q=Prince+When+Doves+Cry"),
        ("Cyndi Lauper", "Girls Just Want to Have Fun", "https://music.youtube.com/search?q=Cyndi+Lauper+Girls+Just+Want+To+Have+Fun"),
        ("Wham!", "Wake Me Up Before You Go-Go", "https://music.youtube.com/search?q=Wham+Wake+Me+Up+Before+You+Go+Go"),
    ],
    1985: [
        ("a-ha", "Take On Me", "https://music.youtube.com/search?q=aha+Take+On+Me"),
        ("Madonna", "Like a Virgin", "https://music.youtube.com/search?q=Madonna+Like+a+Virgin"),
        ("Dire Straits", "Money for Nothing", "https://music.youtube.com/search?q=Dire+Straits+Money+for+Nothing"),
        ("Tears for Fears", "Everybody Wants to Rule the World", "https://music.youtube.com/search?q=Tears+for+Fears+Everybody+Wants+to+Rule+the+World"),
    ],
    1986: [
        ("Peter Gabriel", "Sledgehammer", "https://music.youtube.com/search?q=Peter+Gabriel+Sledgehammer"),
        ("Falco", "Rock Me Amadeus", "https://music.youtube.com/search?q=Falco+Rock+Me+Amadeus"),
        ("Whitney Houston", "Greatest Love of All", "https://music.youtube.com/search?q=Whitney+Houston+Greatest+Love+of+All"),
        ("Simply Red", "Holding Back the Years", "https://music.youtube.com/search?q=Simply+Red+Holding+Back+the+Years"),
    ],
    1987: [
        ("Michael Jackson", "Bad", "https://music.youtube.com/search?q=Michael+Jackson+Bad"),
        ("U2", "With or Without You", "https://music.youtube.com/search?q=U2+With+or+Without+You"),
        ("Whitney Houston", "I Wanna Dance with Somebody", "https://music.youtube.com/search?q=Whitney+Houston+I+Wanna+Dance+with+Somebody"),
        ("Rick Astley", "Never Gonna Give You Up", "https://music.youtube.com/search?q=Rick+Astley+Never+Gonna+Give+You+Up"),
    ],
    1988: [
        ("George Michael", "Faith", "https://music.youtube.com/search?q=George+Michael+Faith"),
        ("Kylie Minogue", "I Should Be So Lucky", "https://music.youtube.com/search?q=Kylie+Minogue+I+Should+Be+So+Lucky"),
        ("INXS", "Never Tear Us Apart", "https://music.youtube.com/search?q=INXS+Never+Tear+Us+Apart"),
        ("Guns N' Roses", "Sweet Child O' Mine", "https://music.youtube.com/search?q=Guns+N+Roses+Sweet+Child+O+Mine"),
    ],
    1989: [
        ("Madonna", "Like a Prayer", "https://music.youtube.com/search?q=Madonna+Like+a+Prayer"),
        ("Roxette", "The Look", "https://music.youtube.com/search?q=Roxette+The+Look"),
        ("Bon Jovi", "Livin' on a Prayer", "https://music.youtube.com/search?q=Bon+Jovi+Livin+on+a+Prayer"),
        ("Soul II Soul", "Back to Life", "https://music.youtube.com/search?q=Soul+II+Soul+Back+to+Life"),
    ],
    1990: [
        ("Sinéad O'Connor", "Nothing Compares 2U", "https://music.youtube.com/search?q=Sinead+Nothing+Compares+2U"),
        ("MC Hammer", "U Can't Touch This", "https://music.youtube.com/search?q=MC+Hammer+U+Cant+Touch+This"),
        ("Madonna", "Vogue", "https://music.youtube.com/search?q=Madonna+Vogue"),
        ("Snap", "The Power", "https://music.youtube.com/search?q=Snap+The+Power"),
    ],
    1991: [
        ("Nirvana", "Smells Like Teen Spirit", "https://music.youtube.com/search?q=Nirvana+Smells+Like+Teen+Spirit"),
        ("Bryan Adams", "Everything I Do", "https://music.youtube.com/search?q=Bryan+Adams+Everything+I+Do"),
        ("R.E.M.", "Losing My Religion", "https://music.youtube.com/search?q=REM+Losing+My+Religion"),
        ("C+C Music Factory", "Gonna Make You Sweat", "https://music.youtube.com/search?q=CC+Music+Factory+Gonna+Make+You+Sweat"),
    ],
    1992: [
        ("Whitney Houston", "I Will Always Love You", "https://music.youtube.com/search?q=Whitney+Houston+I+Will+Always+Love+You"),
        ("Boyz II Men", "End of the Road", "https://music.youtube.com/search?q=Boyz+II+Men+End+of+the+Road"),
        ("TLC", "Ain't 2 Proud 2 Beg", "https://music.youtube.com/search?q=TLC+Aint+2+Proud+2+Beg"),
        ("2 Unlimited", "No Limit", "https://music.youtube.com/search?q=2+Unlimited+No+Limit"),
    ],
    1993: [
        ("Haddaway", "What Is Love", "https://music.youtube.com/search?q=Haddaway+What+Is+Love"),
        ("Ace of Base", "All That She Wants", "https://music.youtube.com/search?q=Ace+of+Base+All+That+She+Wants"),
        ("Janet Jackson", "That's the Way Love Goes", "https://music.youtube.com/search?q=Janet+Jackson+Thats+the+Way+Love+Goes"),
        ("Corona", "The Rhythm of the Night", "https://music.youtube.com/search?q=Corona+Rhythm+of+the+Night"),
    ],
    1994: [
        ("Ace of Base", "The Sign", "https://music.youtube.com/search?q=Ace+of+Base+The+Sign"),
        ("Boyz II Men", "I'll Make Love to You", "https://music.youtube.com/search?q=Boyz+II+Men+Ill+Make+Love+to+You"),
        ("Céline Dion", "The Power of Love", "https://music.youtube.com/search?q=Celine+Dion+Power+of+Love"),
        ("La Bouche", "Be My Lover", "https://music.youtube.com/search?q=La+Bouche+Be+My+Lover"),
    ],
    1995: [
        ("TLC", "Waterfalls", "https://music.youtube.com/search?q=TLC+Waterfalls"),
        ("Oasis", "Wonderwall", "https://music.youtube.com/search?q=Oasis+Wonderwall"),
        ("Coolio", "Gangsta's Paradise", "https://music.youtube.com/search?q=Coolio+Gangstas+Paradise"),
        ("Mariah Carey", "Fantasy", "https://music.youtube.com/search?q=Mariah+Carey+Fantasy"),
    ],
    1996: [
        ("Spice Girls", "Wannabe", "https://music.youtube.com/search?q=Spice+Girls+Wannabe"),
        ("Los Del Rio", "Macarena", "https://music.youtube.com/search?q=Los+Del+Rio+Macarena"),
        ("Alanis Morissette", "Ironic", "https://music.youtube.com/search?q=Alanis+Morissette+Ironic"),
        ("Toni Braxton", "Un-Break My Heart", "https://music.youtube.com/search?q=Toni+Braxton+Un+Break+My+Heart"),
    ],
    1997: [
        ("Spice Girls", "2 Become 1", "https://music.youtube.com/search?q=Spice+Girls+2+Become+1"),
        ("Hanson", "MMMBop", "https://music.youtube.com/search?q=Hanson+MMMBop"),
        ("Elton John", "Candle in the Wind", "https://music.youtube.com/search?q=Elton+John+Candle+in+the+Wind"),
        ("Puff Daddy", "I'll Be Missing You", "https://music.youtube.com/search?q=Puff+Daddy+Ill+Be+Missing+You"),
    ],
    1998: [
        ("Céline Dion", "My Heart Will Go On", "https://music.youtube.com/search?q=Celine+Dion+My+Heart+Will+Go+On"),
        ("Backstreet Boys", "Quit Playing Games", "https://music.youtube.com/search?q=Backstreet+Boys+Quit+Playing+Games"),
        ("Madonna", "Ray of Light", "https://music.youtube.com/search?q=Madonna+Ray+of+Light"),
        ("Brandy & Monica", "The Boy Is Mine", "https://music.youtube.com/search?q=Brandy+Monica+The+Boy+Is+Mine"),
    ],
    1999: [
        ("Backstreet Boys", "I Want It That Way", "https://music.youtube.com/search?q=Backstreet+Boys+I+Want+It+That+Way"),
        ("Cher", "Believe", "https://music.youtube.com/search?q=Cher+Believe"),
        ("TLC", "No Scrubs", "https://music.youtube.com/search?q=TLC+No+Scrubs"),
        ("Ricky Martin", "Livin' La Vida Loca", "https://music.youtube.com/search?q=Ricky+Martin+Livin+La+Vida+Loca"),
    ],
}

# ─── Топ чарты по годам ───────────────────────────────────────────────────────

TOP_CHARTS = {
    1990: ["Sinéad O'Connor - Nothing Compares 2U", "MC Hammer - U Can't Touch This", "Madonna - Vogue", "Phil Collins - Another Day in Paradise"],
    1991: ["Bryan Adams - (Everything I Do) I Do It for You", "Nirvana - Smells Like Teen Spirit", "R.E.M. - Losing My Religion", "C+C Music Factory - Gonna Make You Sweat"],
    1992: ["Whitney Houston - I Will Always Love You", "Sir Mix-A-Lot - Baby Got Back", "Boyz II Men - End of the Road", "TLC - Ain't 2 Proud 2 Beg"],
    1993: ["Haddaway - What Is Love", "2 Unlimited - No Limit", "Ace of Base - All That She Wants", "Janet Jackson - That's the Way Love Goes"],
    1994: ["Ace of Base - The Sign", "Boyz II Men - I'll Make Love to You", "Céline Dion - The Power of Love", "All-4-One - I Swear"],
    1995: ["Mariah Carey - Fantasy", "TLC - Waterfalls", "Coolio - Gangsta's Paradise", "Oasis - Wonderwall"],
    1996: ["Los Del Rio - Macarena", "Spice Girls - Wannabe", "Toni Braxton - Un-Break My Heart", "Alanis Morissette - Ironic"],
    1997: ["Elton John - Candle in the Wind", "Puff Daddy - I'll Be Missing You", "Hanson - MMMBop", "Spice Girls - 2 Become 1"],
    1998: ["Céline Dion - My Heart Will Go On", "Madonna - Ray of Light", "Backstreet Boys - Quit Playing Games", "Brandy & Monica - The Boy Is Mine"],
    1999: ["Cher - Believe", "Backstreet Boys - I Want It That Way", "TLC - No Scrubs", "Ricky Martin - Livin' La Vida Loca"],
}

# ─── Исторические события ─────────────────────────────────────────────────────

HISTORY = {
    1984: [
        "Альбом Thriller Майкла Джексона стал самым продаваемым в истории 🎵",
        "Летние Олимпийские игры в Лос-Анджелесе — праздник спорта 🏅",
        "Apple выпустила первый Macintosh — революция в мире компьютеров 💻",
        "Вышел фильм «Ghostbusters» — хит на все времена 👻",
        "Tetris создан советским программистом Алексеем Пажитновым 🎮",
    ],
    1985: [
        "Live Aid собрал 400 млн зрителей и помог миллионам людей в Африке 🎸",
        "Появился тетрис — самая популярная игра в истории 🎮",
        "Вышел фильм «Назад в будущее» — стал культовым мгновенно 🚗",
        "Nintendo выпустила приставку NES — и дети забыли про улицу 🕹️",
        "Coca-Cola выпустила «New Coke» — и весь мир потребовал вернуть старую 🥤",
    ],
    1986: [
        "Диего Марадона показал лучший гол в истории футбола на ЧМ ⚽",
        "Вышел «Top Gun» с Томом Крузом — все мальчики хотели стать лётчиками ✈️",
        "Pixar основана как независимая студия — будущее анимации началось 🎬",
        "Появился первый компакт-диск в продаже — кассеты начали сдавать позиции 💿",
    ],
    1987: [
        "Первый в мире мобильный звонок — началась эра сотовой связи 📱",
        "Вышел альбом Майкла Джексона «Bad» — снова мировой хит 🎵",
        "Появился первый книжный магазин Amazon — тогда ещё только книги 📚",
        "U2 выпустили «The Joshua Tree» — один из лучших альбомов 80-х 🎸",
        "Рейган и Горбачёв подписали договор о ракетах — мир стал чуть безопаснее 🕊️",
    ],
    1988: [
        "Сеульская Олимпиада — Советский Союз взял 55 золотых медалей 🏅",
        "Pixar выпустила первый компьютерный короткометражный фильм — чудо технологий 🎬",
        "Вышел альбом Guns N' Roses «Appetite for Destruction» — рок-легенда 🎸",
        "Появились первые CD-плееры для дома — музыка зазвучала идеально 💿",
        "Стив Джобс основал NeXT — шаг к возвращению в Apple 💻",
    ],
    1989: [
        "Падение Берлинской стены — люди плакали от радости и обнимались 🧱❤️",
        "Тим Бернерс-Ли изобрёл World Wide Web — интернет для всех 🌐",
        "Вышел «Маленькая русалочка» от Disney — начался ренессанс анимации 🧜‍♀️",
        "Gameboy поступил в продажу — тетрис теперь в кармане 🎮",
        "Тейлор Свифт родилась — будущая поп-королева делает первый вдох 👶",
    ],
    1990: [
        "Объединение Германии — разделённая семья снова вместе 🇩🇪❤️",
        "В Москве открылся первый McDonald's — очередь растянулась на километр 🍔",
        "Вышел «Домашний одиночка» — до сих пор смотрят каждый Новый год 🎄",
        "Запущен телескоп Хаббл — человечество увидело космос по-новому 🔭",
        "Синди Кроуфорд, Наоми Кэмпбелл, Клаудия Шиффер — эпоха супермоделей 💃",
    ],
    1991: [
        "Интернет стал публичным — мир никогда не будет прежним 🌐",
        "Nirvana выпустила «Nevermind» — поколение нашло свой голос 🎸",
        "Вышел «Терминатор 2» — лучший боевик десятилетия 🤖",
        "Появился первый смартфон-прообраз от IBM — будущее в кармане 📱",
        "Queen выступили на Live at Wembley — Фредди Меркьюри зажёг 70 тысяч человек 🎤",
    ],
    1992: [
        "Барселонская Олимпиада — «Dream Team» США с Джорданом покорила баскетбол 🏅",
        "Первый SMS в истории — «Merry Christmas» изменил общение навсегда 📱",
        "Вышел «Аладдин» от Disney — Robin Williams озвучил Джинна гениально 🧞",
        "Билл Клинтон сыграл на саксофоне в прямом эфире — политика стала ближе 🎷",
        "Появился первый веб-браузер — интернет обрёл лицо 🌐",
    ],
    1993: [
        "Jurassic Park вышел в кино — динозавры ожили на экране 🦕",
        "Создан Евросоюз — Европа открыла границы для своих граждан 🇪🇺",
        "Вышел «Список Шиндлера» — фильм, который нужно увидеть каждому 🎬",
        "Whitney Houston записала «I Will Always Love You» — мурашки до сих пор 🎤",
        "Появился Pentium — компьютеры стали по-настоящему быстрыми 💻",
    ],
    1994: [
        "Вышел «Форрест Гамп» — фильм, который заставил весь мир плакать 🍫",
        "Выход Windows 95 — компьютеры пришли в каждый дом 💻",
        "Вышел «Король Лев» — лучший мультфильм Disney всех времён 🦁",
        "Amazon основан Джеффом Безосом — интернет-торговля изменит мир 📦",
        "PlayStation выпущена в Японии — игры вышли на новый уровень 🕹️",
    ],
    1995: [
        "Toy Story — первый полнометражный компьютерный мультфильм в истории 🤠",
        "eBay открылся — каждый стал продавцом и покупателем 🛒",
        "Windows 95 покорила мир — кнопка «Пуск» изменила жизнь 💻",
        "Вышел «Храброе сердце» — Мел Гибсон получил Оскар 🏆",
        "Появился DVD-формат — видеокассеты начали уходить в прошлое 📀",
    ],
    1996: [
        "Олимпиада в Атланте — Россия завоевала 26 золотых медалей 🏅",
        "Вышел «Космический джем» с Майклом Джорданом — мультик для всех поколений 🏀",
        "Тамагочи появился в продаже — все заботились о виртуальном питомце 🐣",
        "Spice Girls выпустили дебютный альбом — Girl Power захватила мир 💃",
        "ICQ выпущен — первый мессенджер для всех 💬",
    ],
    1997: [
        "Titanic вышел в кино — самый кассовый фильм своего времени 🚢",
        "Первый Гарри Поттер вышел из печати — началась магия 📚",
        "Google основан в гараже — скоро изменит всё 🔍",
        "Daft Punk выпустили «Homework» — электронная музыка захватила планету 🎧",
        "Появился первый DVD-плеер в продаже — кино стало домашним 📀",
    ],
    1998: [
        "Google официально запущен — поиск информации стал мгновенным 🔍",
        "Вышел «Спасти рядового Райана» — шедевр Спилберга 🎬",
        "Nokia 5110 стала самым популярным телефоном — у всех в кармане 📱",
        "Вышел «Принц Египта» — один из лучших анимационных фильмов 90-х 🎬",
        "Появился Napster — музыку впервые стали слушать бесплатно онлайн 🎵",
    ],
    1999: [
        "Матрица вышла в кино — и взорвала мозг всему поколению 🕶️",
        "Backstreet Boys выпустили «Millennium» — 40 млн копий разлетелись мгновенно 🎤",
        "Вышел «Шестое чувство» — никто не догадался о финале 👻",
        "MSN Messenger запущен — онлайн-общение стало нормой 💬",
        "Человечество впервые встречало Новый год с надеждой на лучшее тысячелетие 🎆",
    ],
}

# ─── Факты о 90-х ─────────────────────────────────────────────────────────────

FACTS_90S = [
    (
        "🎸 *Как Nirvana убила эпоху за одну ночь*\n\n"
        "В сентябре 1991 года вышел альбом Nevermind. До этого на вершинах чартов "
        "царил глэм-метал — яркие костюмы, начёсы и гитарные соло.\n\n"
        "Через месяц после выхода Nevermind Nirvana вытеснила Michael Jackson с первого "
        "места Billboard. Лейблы в панике начали подписывать гранж-группы.\n\n"
        "Курт Кобейн не хотел такой славы. Он говорил: _'Я не хочу быть Mick Jagger. "
        "Я просто хочу играть музыку.'_\n\n"
        "Но история уже была написана. 🎸",
        "Nirvana Smells Like Teen Spirit"
    ),
    (
        "💿 *Как CD победили кассеты*\n\n"
        "В начале 90-х у каждого был кассетный плеер — Walkman был символом эпохи. "
        "Кассеты жевались, перематывались карандашом, стирались.\n\n"
        "К 1993 году CD обогнали кассеты по продажам. Качество звука было несравнимо лучше. "
        "Но у CD была проблема — они царапались и переставали читаться.\n\n"
        "Тогда никто не знал что через 10 лет придёт MP3 и уничтожит и кассеты и диски. "
        "Эпоха физических носителей уходила навсегда. 💿",
        None
    ),
    (
        "👸 *История Spice Girls — случайность которая покорила мир*\n\n"
        "В 1994 году менеджер Боб Херберт искал девочек для новой группы. "
        "На прослушивание пришли сотни кандидаток.\n\n"
        "Выбрали пятерых совершенно разных девушек. Они почти сразу уволили менеджера "
        "и взяли дела в свои руки — беспрецедентный шаг для новичков.\n\n"
        "Wannabe вышла в 1996 и стала №1 в 37 странах. "
        "Girl Power стал не просто слоганом — целым движением.\n\n"
        "85 миллионов проданных альбомов. Самая продаваемая женская группа в истории. 👸",
        "Spice Girls Wannabe"
    ),
    (
        "⚔️ *Война брит-попа: Oasis vs Blur*\n\n"
        "Лето 1995 года. Два лагеря разделили всю Британию.\n\n"
        "Blur и Oasis специально выпустили синглы в один день — "
        "Country House vs Roll With It. Это было намеренное противостояние.\n\n"
        "Blur победил по продажам — 274 тысячи против 216 тысяч. "
        "Но Oasis смеялся последним — их альбом (What's the Story) Morning Glory? "
        "стал одним из самых продаваемых в истории Британии.\n\n"
        "Лиам Галлахер про Blur: _'Они играют для девочек.'_ "
        "Дэймон Албарн смолчал. 🇬🇧",
        "Oasis Wonderwall"
    ),
    (
        "📺 *MTV — машина которая делала звёзд*\n\n"
        "В 90-х MTV был всем. Если твой клип крутили на MTV — ты становился суперзвездой. "
        "Если нет — тебя не существовало.\n\n"
        "Лейблы тратили миллионы на клипы. Michael Jackson снял Thriller за $500,000 — "
        "огромные деньги по тем временам.\n\n"
        "Pearl Jam в знак протеста отказались снимать клипы в 1994. "
        "Их всё равно слушали миллионы — но это был редкий случай.\n\n"
        "К концу 90-х MTV почти перестал показывать музыку. "
        "Реалити-шоу оказались дешевле. Эпоха закончилась. 📺",
        "Michael Jackson Thriller"
    ),
    (
        "💔 *Курт Кобейн — человек который не хотел быть легендой*\n\n"
        "Nirvana стала символом поколения против воли своего лидера. "
        "Кобейн ненавидел коммерческий успех и чувствовал себя предателем.\n\n"
        "На церемонию MTV Awards он вышел в больничном халате. "
        "На Грэмми отказывался идти. Говорил что хочет играть маленькие клубы.\n\n"
        "В апреле 1994 года его не стало. Ему было 27 лет.\n\n"
        "Куртни Лав зачитала его предсмертную записку на публике. "
        "_'Лучше сгореть, чем угаснуть.'_ "
        "Эту фразу он взял у Нила Янга. 💔",
        "Nirvana Come As You Are"
    ),
    (
        "🕺 *Macarena — песня которую ненавидели и не могли остановить*\n\n"
        "Los Del Rio записали Macarena в 1993 году в Венесуэле. "
        "Три года песня была никому не известна.\n\n"
        "В 1996 вышел ремикс с английскими куплетами — и мир сошёл с ума. "
        "14 недель на первом месте Billboard Hot 100. Рекорд для иностранной песни.\n\n"
        "На съезде Демократической партии США 20,000 делегатов танцевали Macarena. "
        "Хиллари Клинтон тоже танцевала.\n\n"
        "Музыкальные критики её ненавидели. Народ обожал. 🕺",
        "Los Del Rio Macarena"
    ),
    (
        "💻 *Napster — студент который взорвал музыкальную индустрию*\n\n"
        "В 1999 году 19-летний студент Шон Фэннинг написал программу за несколько недель. "
        "Napster позволял бесплатно скачивать музыку.\n\n"
        "Через год — 80 миллионов пользователей. Лейблы в панике подали в суд.\n\n"
        "Metallica лично предоставила список из 335,000 пользователей "
        "которых требовала заблокировать. Их возненавидели фанаты.\n\n"
        "В 2001 году Napster закрыли. Но джин был выпущен из бутылки — "
        "люди поняли что музыка может быть бесплатной. "
        "Индустрия уже никогда не будет прежней. 💻",
        "Metallica Enter Sandman"
    ),
    (
        "🎸 *OK Computer — альбом из будущего записанный в 1997*\n\n"
        "Radiohead записывали OK Computer в особняке где снимали фильм ужасов. "
        "Том Йорк говорил что чувствовал себя на грани нервного срыва.\n\n"
        "Альбом пел о технологиях, отчуждении и конце человечности — "
        "в 1997 году это казалось фантастикой.\n\n"
        "Сейчас эти слова звучат как репортаж из 2024 года.\n\n"
        "Rolling Stone назвал его лучшим альбомом 90-х. "
        "Многие называют лучшим альбомом всех времён. 🎸",
        "Radiohead Paranoid Android"
    ),
    (
        "🇷🇺 *Виктор Цой — стена которая не молчит*\n\n"
        "15 августа 1990 года Виктор Цой погиб в автокатастрофе в Латвии. "
        "Ему было 28 лет.\n\n"
        "На следующий день на Арбате в Москве появилась надпись: "
        "_'Цой жив'_. Стена до сих пор существует.\n\n"
        "Его песни стали гимном перемен. _'Перемен требуют наши сердца'_ "
        "звучало на митингах по всему СССР.\n\n"
        "Последний альбом Кино вышел уже после его гибели. "
        "Он называется просто — *Чёрный альбом*. 🖤",
        "Кино Перемен"
    ),
    (
        "🎤 *Auto-Tune: как Cher случайно изменила музыку*\n\n"
        "В 1998 году продюсер Марк Тейлор использовал новый плагин для коррекции вокала "
        "на песне Believe.\n\n"
        "Он случайно выкрутил параметр до максимума — и получился тот самый "
        "роботизированный звук голоса.\n\n"
        "Поначалу все думали что это синтезатор. Продюсеры скрывали что используют "
        "Auto-Tune — боялись что сочтут мошенниками.\n\n"
        "Сегодня Auto-Tune используется в 90% поп-музыки. "
        "T-Pain превратил его в искусство. "
        "Всё началось с той случайной ошибки на записи Cher. 🎤",
        "Cher Believe"
    ),
    (
        "📟 *Пейджер — Telegram девяностых*\n\n"
        "До мобильников у каждого уважающего себя подростка был пейджер. "
        "Сообщения передавались через оператора — ты звонил и диктовал текст.\n\n"
        "Существовал целый код цифр: 143 значило 'я тебя люблю' (по числу букв в словах), "
        "07734 перевёрнутый читался как 'hello'.\n\n"
        "К 1999 году пейджеры исчезли почти полностью — мобильные телефоны подешевели. "
        "Эпоха длилась меньше десяти лет, но осталась легендой. 📟",
        None
    ),
    (
        "🎒 *Walkman и первые наушники-таблетки*\n\n"
        "Sony Walkman появился ещё в 80-х, но именно в 90-х он стал по-настоящему массовым — "
        "каждый школьник носил его в рюкзаке.\n\n"
        "Батарейки AA садились за пару часов, поэтому запасные всегда лежали в кармане. "
        "Перемотка карандашом, чтобы не сажать мотор — целый ритуал.\n\n"
        "В 1992 вышел первый CD-Walkman, но кассетный вариант жил ещё долго — "
        "он был дешевле и прочнее. 🎒",
        None
    ),
    (
        "💃 *Ace of Base — шведы, покорившие весь мир*\n\n"
        "В 1993 году шведская группа выпустила альбом Happy Nation. "
        "В США он вышел под названием The Sign и стал самым продаваемым дебютом года.\n\n"
        "Песня The Sign держалась на первом месте Billboard 6 недель подряд. "
        "Продюсеры сначала не верили в успех — звучание казалось слишком простым.\n\n"
        "Итог: больше 30 миллионов проданных копий альбома по всему миру. 💃",
        "Ace of Base The Sign"
    ),
    (
        "🍼 *Barbie Girl — песня, которую засудила Mattel*\n\n"
        "В 1997 году датско-норвежская группа Aqua выпустила Barbie Girl. "
        "Она стала абсолютным летним хитом — и абсолютным раздражителем для компании Mattel.\n\n"
        "Производитель кукол подал в суд за использование образа Барби без разрешения. "
        "Судья отклонил иск, заявив, что песня — это пародия, защищённая правом на самовыражение.\n\n"
        "Судебное решение вошло в учебники по авторскому праву как классический пример. 🍼",
        "Aqua Barbie Girl"
    ),
    (
        "🎤 *Whitney Houston и голос, который сломал шкалу*\n\n"
        "В 1992 году вышел саундтрек к фильму 'Телохранитель'. "
        "Заглавная песня I Will Always Love You стала визитной карточкой всей эпохи.\n\n"
        "Знаменитая пауза перед финальным куплетом — тишина длиной в целую секунду — "
        "была предложена продюсером Дэвидом Фостером прямо в студии.\n\n"
        "Сингл провёл 14 недель на первом месте Billboard — рекорд, который держался годами. 🎤",
        "Whitney Houston I Will Always Love You"
    ),
    (
        "🖤 *Metallica — чёрный альбом, расколовший фанатов*\n\n"
        "В 1991 году Metallica выпустила самоназванный альбом с чёрной обложкой. "
        "Звучание стало проще и мелодичнее прежнего трэш-метала группы.\n\n"
        "Часть старых фанатов обвинила группу в 'продаже' мейнстриму. "
        "Но именно этот альбом принёс Metallica мировую популярность за пределами метал-сцены.\n\n"
        "Продано свыше 30 миллионов копий — это самый продаваемый альбом 90-х в США вообще, "
        "независимо от жанра. 🖤",
        "Metallica Enter Sandman"
    ),
    (
        "🌀 *Radiohead и альбом, который никто не понял сразу*\n\n"
        "После успеха сингла Creep в 1993 году от Radiohead ждали ещё поп-рока. "
        "Вместо этого группа выпустила мрачный, тревожный The Bends, а затем OK Computer.\n\n"
        "Лейбл боялся, что альбом провалится — слишком сложный, слишком странный. "
        "Критики поначалу тоже терялись в оценках.\n\n"
        "Сегодня OK Computer стабильно входит в списки величайших альбомов всех времён. 🌀",
        "Radiohead Creep"
    ),
    (
        "🩸 *2Pac и противостояние побережий*\n\n"
        "Середина 90-х — расцвет хип-хопа и жёсткое соперничество Западного и Восточного побережья США. "
        "2Pac и The Notorious B.I.G. когда-то дружили, но пресса и лейблы раздули конфликт.\n\n"
        "В 1996 году 2Pac был застрелен в Лас-Вегасе. Через полгода та же участь постигла Biggie. "
        "Обе смерти до сих пор официально не раскрыты полностью.\n\n"
        "Трагедия изменила индустрию хип-хопа — многие артисты начали демонстративно "
        "отказываться от конфликтов ради конфликтов. 🩸",
        "2Pac California Love"
    ),
    (
        "🎧 *Prodigy и рождение биг-бита*\n\n"
        "Альбом The Fat of the Land 1997 года взорвал чарты сразу в нескольких странах. "
        "Клип на Firestarter шокировал зрителей и был запрещён к показу на MTV в дневное время.\n\n"
        "Группа выросла из рейв-культуры английских полей и заброшенных складов начала 90-х. "
        "Prodigy одними из первых доказали, что электронная музыка может звучать агрессивно, как рок.\n\n"
        "The Fat of the Land стал первым электронным альбомом, дебютировавшим на первом месте "
        "чартов США и Британии одновременно. 🎧",
        "Prodigy Firestarter"
    ),
    (
        "👑 *Mariah Carey и диапазон в пять октав*\n\n"
        "В 1990 году 20-летняя Мэрайя Кэри выпустила дебютный альбом и сразу стала звездой. "
        "Её голос охватывал почти пять октав — редкость даже среди профессиональных вокалистов.\n\n"
        "К середине 90-х она уже была самой продаваемой солисткой десятилетия в США. "
        "Песня Fantasy 1995 года стала первым синглом женщины-артиста, дебютировавшим на 1 месте Billboard.\n\n"
        "До этого рекорда добивались только группы, но не сольные исполнительницы. 👑",
        "Mariah Carey Fantasy"
    ),
    (
        "🧢 *Backstreet Boys и фабрика бойз-бендов*\n\n"
        "В 1993 году продюсер Лу Перлман начал собирать группу из талантливых подростков Орландо. "
        "Первый альбом в США почти не заметили — успех пришёл из Европы и Азии.\n\n"
        "Только в 1997 году, после переиздания, Backstreet Boys покорили и американский рынок. "
        "Модель Перлмана — кастинг, хореография, безупречный имидж — стала шаблоном для индустрии.\n\n"
        "По этой же схеме позже был собран NSYNC — их главный конкурент и, по слухам, "
        "источник многолетней судебной тяжбы с тем же продюсером. 🧢",
        "Backstreet Boys Everybody"
    ),
    (
        "🕶️ *Дискотека Авария и рождение русского стёба*\n\n"
        "Ростовская группа появилась в 1994 году с ироничными, почти абсурдными текстами. "
        "Песня 'Тачка' и другие хиты звучали на каждой городской дискотеке.\n\n"
        "Группа сознательно избегала серьёзности — на фоне лирического русского рока это "
        "выглядело как глоток свежего воздуха.\n\n"
        "Формат 'смешно и танцевально' оказался настолько удачным, что определил "
        "целое направление поп-музыки конца десятилетия. 🕶️",
        "Дискотека Авария Тачка"
    ),
    (
        "🐺 *Мумий Тролль и новый звук русского рока*\n\n"
        "Илья Лагутенко привёз во Владивосток идеи британского брит-попа и наложил их "
        "на русский язык. Альбом 'Морская' 1997 года прозвучал абсолютно не похоже на всё вокруг.\n\n"
        "Песня 'Владивосток 2000' стала неформальным гимном целого поколения. "
        "Критики поначалу не знали, куда отнести эту музыку — слишком легко для рока, "
        "слишком странно для попсы.\n\n"
        "В итоге жанр так и назвали — просто 'Мумий Тролль'. Уникальный случай, "
        "когда группа сама стала жанром. 🐺",
        "Мумий Тролль Владивосток 2000"
    ),
    (
        "🎬 *MTV и бюджеты клипов, которые превышали бюджет фильмов*\n\n"
        "К середине 90-х клипы стали полноценным видом искусства. "
        "Michael Jackson потратил на клип Scream 1995 года 7 миллионов долларов — "
        "рекорд, который держался годами.\n\n"
        "Режиссёры клипов — вроде Spike Jonze или Michel Gondry — становились звёздами "
        "не меньше самих музыкантов.\n\n"
        "MTV Video Music Awards превратились в главное шоу года, где скандалы значили "
        "не меньше, чем сами награды. 🎬",
        None
    ),
    (
        "📻 *Формат Now That's What I Call Music и культура сборников*\n\n"
        "В 90-х пик популярности переживали сборники хитов на кассетах и CD — "
        "по несколько десятков треков разных исполнителей в одном альбоме.\n\n"
        "Их покупали не ради конкретного артиста, а чтобы иметь под рукой 'всё, что играет по радио'. "
        "Это была эпоха до плейлистов — сборник был единственным способом собрать любимые песни вместе.\n\n"
        "Такие сборники расходились миллионными тиражами и часто продавались лучше "
        "сольных альбомов звёзд. 📻",
        None
    ),
    (
        "🌐 *ICQ и первый звук интернета*\n\n"
        "В 1996 году три израильских программиста выпустили ICQ — первый массовый интернет-мессенджер. "
        "Характерный звук 'уся-уся' при новом сообщении стал одним из символов конца эпохи.\n\n"
        "К концу 90-х у ICQ было больше 100 миллионов пользователей по всему миру. "
        "Люди указывали любимую музыку прямо в профиле — задолго до появления стриминговых сервисов.\n\n"
        "Именно через такие чаты подростки впервые начали массово обмениваться MP3-файлами. 🌐",
        None
    ),
    (
        "🎹 *Земфира и взрыв женского рока в России*\n\n"
        "Дебютный альбом Земфиры вышел в 1999 году и мгновенно разошёлся на цитаты. "
        "Резкий, нервный вокал и откровенные тексты звучали непривычно для эстрады того времени.\n\n"
        "До этого женский рок в России ассоциировался в основном с бардовской традицией. "
        "Земфира сломала этот образ полностью — и открыла дорогу целой волне похожих исполнительниц.\n\n"
        "Альбом стал платиновым в первый же год — редкость для дебюта в то время. 🎹",
        "Земфира СПИД"
    ),
    (
        "🚀 *Napster и день, когда индустрия испугалась будущего*\n\n"
        "Хотя сервис появился только в 1999 году, идея бесплатного обмена музыкой "
        "витала в воздухе весь предыдущий десяток лет — благодаря росту домашнего интернета.\n\n"
        "За 2 года у Napster набралось 80 миллионов пользователей. "
        "Крупные лейблы подали иски один за другим, но джинн уже выбрался из бутылки.\n\n"
        "90-е закончились последним десятилетием, когда музыку в основном покупали, "
        "а не скачивали бесплатно. 🚀",
        None
    ),
    (
        "🎸 *Оазис и Blur делили не только чарты, но и обложки газет*\n\n"
        "Летом 1995 года синглы двух групп — Country House у Blur и Roll With It у Oasis — "
        "вышли в один день. Британская пресса окрестила это 'Битвой брит-попа'.\n\n"
        "Формально победил Blur — их сингл занял первое место в чартах. "
        "Но в долгосрочной перспективе именно Oasis стали культовой группой поколения.\n\n"
        "Лидеры групп годами публично обменивались колкостями в интервью — "
        "конфликт подогревал интерес прессы не хуже самой музыки. 🎸",
        "Oasis Wonderwall"
    ),
    (
        "🎮 *Музыка в видеоиграх стала серьёзным жанром*\n\n"
        "В 90-х саундтреки к играм вроде Final Fantasy VII или Doom обрели самостоятельную "
        "популярность — их слушали отдельно от самих игр.\n\n"
        "Композитор Нобуо Уэмацу для Final Fantasy писал полноценные оркестровые партитуры, "
        "хотя техника того времени поддерживала лишь примитивный синтезированный звук.\n\n"
        "Позже именно эти саундтреки легли в основу целого направления — "
        "оркестровых концертов игровой музыки, которые собирают стадионы до сих пор. 🎮",
        None
    ),
    (
        "🕺 *No Doubt и путь от панка к попу*\n\n"
        "Группа с Гвен Стефани начинала как локальная ска-панк команда Калифорнии в 80-х. "
        "Успех пришёл только в 1995 году с альбомом Tragic Kingdom.\n\n"
        "Песня Don't Speak, написанная после разрыва Гвен с басистом группы, "
        "стала одной из самых узнаваемых баллад десятилетия.\n\n"
        "Альбом разошёлся тиражом более 16 миллионов копий — совершенно неожиданный "
        "результат для команды, которую лейбл почти бросил после провала первой пластинки. 🕺",
        "No Doubt Don't Speak"
    ),
    (
        "📼 *MiniDisc — технология, которая опоздала*\n\n"
        "Sony выпустила MiniDisc в 1992 году как замену и кассетам, и CD — компактный, "
        "перезаписываемый, устойчивый к царапинам формат.\n\n"
        "Технически MiniDisc был лучше конкурентов почти во всём. Но высокая цена "
        "устройств и слабая поддержка со стороны других производителей помешали ему захватить рынок.\n\n"
        "В итоге формат остался нишевым увлечением аудиофилов, пока его окончательно "
        "не вытеснили MP3-плееры в начале 2000-х. 📼",
        None
    ),
    (
        "🎺 *TLC и альбом, который принёс убытки при рекордных продажах*\n\n"
        "Альбом CrazySexyCool 1994 года разошёлся тиражом более 11 миллионов копий в США. "
        "При этом сама группа объявила о банкротстве вскоре после релиза.\n\n"
        "Причина — грабительские условия контракта с лейблом: артисты получали "
        "крошечный процент от продаж, а расходы на продюсирование вычитались из их доли.\n\n"
        "История TLC стала одним из самых известных примеров несправедливых контрактов "
        "и позже заставила многих музыкантов пересмотреть условия сделок. 🎺",
        "TLC Waterfalls"
    ),
    (
        "🌍 *Live Aid вдохновил волну благотворительных концертов*\n\n"
        "Хотя сам Live Aid прошёл ещё в 1985 году, именно в 90-х формат массовых "
        "благотворительных суперконцертов расцвёл окончательно — Free Tibet, Tibetan Freedom Concert, "
        "Net Aid.\n\n"
        "На таких мероприятиях впервые массово объединялись артисты совершенно разных жанров "
        "на одной сцене — от панка до попсы.\n\n"
        "Это заложило традицию, которая продолжается до сих пор — от Live 8 до современных "
        "благотворительных стримов. 🌍",
        None
    ),
    (
        "🎤 *Дискотека 90-х и караоке-бум*\n\n"
        "Караоке пришло в Россию и Европу из Японии в начале 90-х и мгновенно стало "
        "массовым развлечением — караоке-бары открывались в каждом крупном городе.\n\n"
        "Продавцы техники сообщали о буме караоке-систем для дома — целые семьи "
        "устраивали вечера пения хитов из чартов.\n\n"
        "Именно караоке-культура 90-х подготовила почву для позже возникших телешоу "
        "талантов вроде Star Academy и Фабрики звёзд. 🎤",
        None
    ),
    (
        "🖤 *Смэшинг Пампкинс и альбом-эксперимент на два диска*\n\n"
        "В 1995 году группа выпустила Mellon Collie and the Infinite Sadness — "
        "двойной альбом с 28 треками, что было редкостью для рок-групп того времени.\n\n"
        "Лидер группы Билли Корган настоял на таком объёме против воли лейбла, "
        "который боялся, что публика не осилит два часа музыки за раз.\n\n"
        "Альбом стал платиновым шесть раз подряд и считается одним из лучших "
        "рок-альбомов десятилетия. 🖤",
        "Smashing Pumpkins 1979"
    ),
    (
        "🎧 *Fatboy Slim и большой биг-бит взрыв*\n\n"
        "Норман Кук, бывший басист The Housemartins, в 1996 году под псевдонимом "
        "Fatboy Slim выпустил Better Living Through Chemistry.\n\n"
        "Его сэмплерный, танцевальный стиль стал визитной карточкой целого британского "
        "клубного направления второй половины 90-х.\n\n"
        "Клип на Praise You 1998 года — снятый одним дублем на улице без разрешения "
        "прохожих — стал классикой независимого музыкального видео. 🎧",
        "Fatboy Slim Praise You"
    ),
    (
        "🎸 *Green Day и панк, который снова стал мейнстримом*\n\n"
        "Альбом Dookie 1994 года вернул панк-рок в чарты после почти двадцатилетнего затишья. "
        "Трек Basket Case стал гимном подросткового бунта нового поколения.\n\n"
        "Часть олдскульной панк-сцены обвинила Green Day в 'продаже' — похожая история "
        "случилась годом ранее с Metallica.\n\n"
        "Тем не менее Dookie разошёлся тиражом свыше 20 миллионов копий и заново "
        "открыл жанр для массовой аудитории. 🎸",
        "Green Day Basket Case"
    ),
    (
        "📺 *Music Television и первые музыкальные реалити-шоу*\n\n"
        "В 1992 году MTV запустила шоу The Real World — прообраз всех современных "
        "реалити-шоу. Формат быстро переняли и музыкальные программы.\n\n"
        "К концу 90-х появились форматы вроде Making the Band, где зрители наблюдали "
        "за самим процессом сборки поп-группы с нуля.\n\n"
        "Эта прозрачность процесса — от кастинга до дебютного сингла — навсегда "
        "изменила отношение публики к поп-музыке как индустрии. 📺",
        None
    ),
    (
        "🎼 *Оффспринг и альбом, разошедшийся без крупного лейбла*\n\n"
        "Альбом Smash 1994 года был выпущен независимым лейблом Epitaph "
        "с крошечным по меркам индустрии бюджетом.\n\n"
        "Несмотря на это, альбом разошёлся тиражом более 11 миллионов копий — "
        "рекорд среди независимых релизов, который не побит до сих пор.\n\n"
        "Успех Smash доказал индустрии, что группа может стать суперзвездой "
        "и без поддержки крупного лейбла. 🎼",
        "The Offspring Self Esteem"
    ),
    (
        "🎙️ *Fugees и альбом, объединивший хип-хоп и мелодику*\n\n"
        "The Score 1996 года смешал рэп с соул-звучанием и кавер-версиями классики — "
        "самая известная из них, Killing Me Softly, была переосмыслением песни Roberta Flack.\n\n"
        "Альбом стал одним из первых хип-хоп релизов, получивших признание "
        "далеко за пределами хип-хоп аудитории — вплоть до пожилых слушателей.\n\n"
        "Продано свыше 22 миллионов копий по всему миру — рекорд для группового "
        "хип-хоп альбома того времени. 🎙️",
        "Fugees Killing Me Softly"
    ),
    (
        "🎵 *Ленинград и рождение матерного шансон-панка*\n\n"
        "Группа Сергея Шнурова образовалась в 1997 году в Петербурге и сразу выделилась "
        "нецензурными текстами и духовой секцией, нетипичной для рок-групп.\n\n"
        "Первые концерты проходили в маленьких клубах, а песни распространялись "
        "буквально из рук в руки на кассетах.\n\n"
        "К концу десятилетия группа уже собирала залы — редкий случай, когда "
        "андеграундный формат стал массовым без всякой ротации на радио. 🎵",
        "Ленинград WWW"
    ),
    (
        "🎬 *Titanic и саундтрек, который побил все рекорды*\n\n"
        "Песня My Heart Will Go On Селин Дион, написанная для фильма 1997 года, "
        "изначально не должна была войти в картину — режиссёр Джеймс Кэмерон "
        "поначалу был против песни с вокалом в фильме.\n\n"
        "Композитор Джеймс Хорнер записал демо-версию тайно, за спиной Кэмерона, "
        "и показал только когда убедился в её силе.\n\n"
        "Сингл провёл недели на первых строчках чартов по всему миру, "
        "а саундтрек стал одним из самых продаваемых в истории. 🎬",
        "Celine Dion My Heart Will Go On"
    ),
    (
        "🥁 *Wu-Tang Clan и стратегия соло-карьер внутри группы*\n\n"
        "Дебютный альбом 1993 года Enter the Wu-Tang собрал девять рэперов сразу. "
        "Их менеджер RZA придумал уникальную бизнес-модель — каждый участник "
        "мог выпускать сольные альбомы на разных лейблах.\n\n"
        "Это позволило группе буквально захватить хип-хоп индустрию сразу с нескольких "
        "фронтов в середине 90-х.\n\n"
        "Схема оказалась настолько успешной, что её позже копировали десятки других "
        "коллективов по всему миру. 🥁",
        "Wu-Tang Clan C.R.E.A.M."
    ),
    (
        "🎈 *Руки Вверх и формула простого счастья*\n\n"
        "Дуэт Сергея Жукова появился в 1997 году с песней '18 мне уже' — "
        "простой, запоминающейся, максимально попадающей в подростковую аудиторию.\n\n"
        "Формула сработала настолько хорошо, что группа за пару лет выпустила "
        "несколько альбомов подряд без потери популярности.\n\n"
        "Их песни до сих пор остаются одними из самых узнаваемых символов "
        "русской танцевальной музыки конца 90-х. 🎈",
        "Руки Вверх 18 мне уже"
    ),
    (
        "🎹 *Enigma и рождение нью-эйдж хитов*\n\n"
        "В 1990 году немецкий проект Enigma выпустил Sadeness Part I — "
        "смесь григорианских песнопений с танцевальным битом.\n\n"
        "Никто в индустрии не верил, что такая необычная смесь может стать хитом — "
        "но песня возглавила чарты сразу нескольких европейских стран.\n\n"
        "Enigma фактически создали новый жанр на стыке эмбиента и данс-музыки, "
        "который позже вдохновил десятки похожих проектов. 🎹",
        "Enigma Sadeness"
    ),
    (
        "🎤 *Alanis Morissette и альбом одной ярости*\n\n"
        "Jagged Little Pill 1995 года был написан почти полностью автобиографично — "
        "об одном конкретном разрыве отношений и обиде на индустрию.\n\n"
        "Лейблы поначалу сомневались в успехе — слишком личный, слишком злой "
        "материал для поп-исполнительницы.\n\n"
        "Альбом разошёлся тиражом свыше 33 миллионов копий и стал одним "
        "из самых продаваемых дебютов в истории женской музыки. 🎤",
        "Alanis Morissette Ironic"
    ),
    (
        "🎸 *Red Hot Chili Peppers и возвращение после трагедии*\n\n"
        "После смерти гитариста Хиллела Словака от передозировки в 1988 году "
        "группа едва не распалась. Новый гитарист Джон Фрушанте помог им "
        "выпустить Blood Sugar Sex Magik в 1991 году.\n\n"
        "Альбом стал прорывом — смесь фанка, панка и психоделии нашла "
        "огромную аудиторию далеко за пределами их прежней ниши.\n\n"
        "Under the Bridge, самая личная песня альбома о борьбе с зависимостью, "
        "неожиданно стала главным хитом — против ожиданий самой группы. 🎸",
        "Red Hot Chili Peppers Under the Bridge"
    ),
    (
        "🎻 *Sixpence None the Richer и хит, который сняли с полки на два года*\n\n"
        "Песня Kiss Me была записана в 1997 году, но обрела популярность только "
        "в 1998-м, после того как попала в саундтрек подросткового фильма.\n\n"
        "До этого лейбл группы обанкротился, и песня чуть было не осталась "
        "неизданной вовсе.\n\n"
        "После взлёта популярности сингл разошёлся тиражом в миллионы копий "
        "и стал одной из самых узнаваемых баллад конца десятилетия. 🎻",
        "Sixpence None the Richer Kiss Me"
    ),
    (
        "📀 *DVD и первые попытки цифрового видео потеснить музыку*\n\n"
        "Формат DVD появился в 1996 году и изначально задумывался как замена "
        "видеокассетам, но музыкальная индустрия быстро начала выпускать на нём "
        "концертные записи.\n\n"
        "Качество картинки и звука было несравнимо лучше VHS — впервые "
        "концертный альбом можно было буквально пересматривать как кино.\n\n"
        "К концу десятилетия концертные DVD стали обязательным дополнением "
        "к турам крупных артистов. 📀",
        None
    ),
    (
        "🎷 *Смуфановая революция Massive Attack*\n\n"
        "Альбом Blue Lines 1991 года считается точкой рождения жанра трип-хоп — "
        "медленной, атмосферной смеси хип-хопа, соула и электроники.\n\n"
        "Бристольская сцена, откуда вышла группа, стала настолько влиятельной, "
        "что породила целое направление — от Portishead до Tricky.\n\n"
        "Позже этот звук стал неотъемлемой частью саундтреков к фильмам "
        "и рекламе на десятилетия вперёд. 🎷",
        "Massive Attack Unfinished Sympathy"
    ),
    (
        "🌊 *Наутилус Помпилиус — прощальный альбом эпохи*\n\n"
        "В 1997 году свердловская группа выпустила альбом 'Атлантида' и объявила о распаде. "
        "Вячеслав Бутусов ушёл, чтобы избежать превращения в 'группу по инерции'.\n\n"
        "Песни вроде 'Крылья' и 'Скованные одной цепью' к тому моменту уже стали "
        "неофициальными гимнами перестроечного поколения.\n\n"
        "Распад на пике популярности был редкостью для российской сцены — "
        "большинство групп тянули карьеру до последнего. 🌊",
        "Наутилус Помпилиус Крылья"
    ),
    (
        "🎻 *Агата Кристи и мрачный гламур 90-х*\n\n"
        "Братья Самойловы построили карьеру на контрасте — театральность, декаданс "
        "и мрачная эстетика на фоне общей энергии рок-сцены начала 90-х.\n\n"
        "Альбом 'Опиум' 1995 года стал одним из самых стилистически смелых "
        "релизов российской рок-музыки того времени.\n\n"
        "Группа одной из первых в России начала уделять серьёзное внимание "
        "визуальному образу и клипам, а не только музыке. 🎻",
        "Агата Кристи Опиум"
    ),
    (
        "🌪️ *Сплин и меланхолия конца десятилетия*\n\n"
        "Александр Васильев основал группу в Петербурге, и уже дебютный альбом "
        "'Пыльная быль' 1997 года выделялся необычно поэтичными текстами.\n\n"
        "Второй альбом 'Гнездо перелётной птицы' 1999 года с песней 'Орбит без сахара' "
        "принёс группе настоящую массовую известность.\n\n"
        "Сплин стал одной из немногих рок-групп конца 90-х, сумевших звучать "
        "одновременно интеллектуально и попадать в народную ротацию. 🌪️",
        "Сплин Орбит без сахара"
    ),
    (
        "🎸 *ДДТ и голос совести русского рока*\n\n"
        "Юрий Шевчук и группа ДДТ уже были легендами к началу 90-х, "
        "но именно в этом десятилетии они окончательно закрепили статус "
        "самой социально острой группы страны.\n\n"
        "Альбом 'Актриса Весна' 1992 года и последующие релизы поднимали темы "
        "войны, несправедливости и распада старого мира без всякой цензуры.\n\n"
        "Шевчук принципиально отказывался от коммерческих компромиссов, "
        "что сделало ДДТ символом честности на фоне расцветающего шоу-бизнеса. 🎸",
        "ДДТ Актриса Весна"
    ),
    (
        "🎤 *Ирина Аллегрова и королева русской эстрады*\n\n"
        "К середине 90-х Аллегрова стала одной из самых титулованных исполнительниц "
        "страны — премия 'Овация' присуждалась ей несколько лет подряд.\n\n"
        "Песня 'Младший лейтенант' 1995 года стала одним из главных эстрадных "
        "хитов десятилетия, растиражированным на кассетах по всей стране.\n\n"
        "Её сценический образ — драматичный, театральный — задал стандарт "
        "для целого поколения российских поп-исполнительниц. 🎤",
        "Ирина Аллегрова Младший лейтенант"
    ),
    (
        "🎧 *На-На и первый российский бойз-бенд*\n\n"
        "Продюсер Бари Алибасов собрал группу На-На в 1989 году, "
        "но настоящий расцвет пришёлся именно на первую половину 90-х.\n\n"
        "Яркие костюмы, синхронная хореография и легко запоминающиеся припевы — "
        "На-На фактически повторили формулу западных бойз-бендов на несколько лет раньше "
        "их массового прихода в Россию.\n\n"
        "Группа регулярно меняла состав, но образ и формула оставались неизменными "
        "на протяжении всего десятилетия. 🎧",
        "На-На Фаина"
    ),
    (
        "🎷 *Отпетые Мошенники и одесский стиль в поп-музыке*\n\n"
        "Группа появилась в 1996 году с характерным залихватским звучанием, "
        "смешивающим поп с интонациями одесского шансона.\n\n"
        "Песня 'Люби меня, люби' и другие хиты быстро стали классикой "
        "русских дискотек конца 90-х.\n\n"
        "Юмористический, слегка ироничный тон текстов выгодно выделял группу "
        "на фоне более серьёзной поп-сцены того времени. 🎷",
        "Отпетые Мошенники Люби меня люби"
    ),
    (
        "🎹 *Технология и синти-поп по-русски*\u200b\n\n"
        "Группа Технология собралась в 1990 году и стала одним из первых "
        "российских проектов, серьёзно работавших в жанре синти-поп.\n\n"
        "Песня 'Нажми на кнопку' 1991 года стала настоящим прорывом — "
        "непривычное электронное звучание резко контрастировало с гитарным роком той эпохи.\n\n"
        "Группа одной из первых в стране начала уделять внимание сложным "
        "сценическим костюмам и футуристичному визуальному стилю. 🎹",
        "Технология Нажми на кнопку"
    ),
    (
        "🎬 *Иванушки International и поп-феномен 1996 года*\n\n"
        "Продюсер Игорь Матвиенко собрал группу специально под формат "
        "лёгкой, позитивной поп-музыки — на контрасте с мрачноватым роком начала десятилетия.\n\n"
        "Песня 'Тополиный пух' стала одним из самых узнаваемых хитов лета 1996 года "
        "и до сих пор считается неофициальным гимном конца учебного года.\n\n"
        "Формула сработала настолько хорошо, что группа почти сразу стала "
        "одной из самых кассовых на российской сцене. 🎬",
        "Иванушки International Тополиный пух"
    ),
    (
        "🎺 *Король и Шут и рождение русского панк-рок-театра*\n\n"
        "Петербургская группа Михаила Горшенёва появилась в начале 90-х "
        "с уникальным сочетанием панк-рока, фолка и хоррор-эстетики.\n\n"
        "Альбом 'Камнем по голове' 1997 года и последующие релизы принесли группе "
        "культовый статус — концерты превращались в настоящие костюмированные шоу.\n\n"
        "КиШ стали одной из немногих групп, чей визуальный образ был "
        "так же важен для успеха, как и сама музыка. 🎺",
        "Король и Шут Прыгну со скалы"
    ),
    (
        "🎸 *Чайф и уральский рок без прикрас*\n\n"
        "Группа Владимира Шахрина к 90-м уже была одной из главных на свердловской "
        "рок-сцене, но именно в этом десятилетии пришла общероссийская известность.\n\n"
        "Альбом 'Дети гор' 1994 года с песней 'Оранжевое настроение' "
        "стал одним из самых душевных релизов российского рока того времени.\n\n"
        "Простые, честные тексты про повседневную жизнь резко выделяли Чайф "
        "на фоне более пафосных рок-групп 90-х. 🎸",
        "Чайф Оранжевое настроение"
    ),
    (
        "🎶 *Гости из будущего и переход к 2000-м*\n\n"
        "Группа Techno-cool, позже сменившая название на 'Гости из будущего', "
        "образовалась в самом конце 90-х в Ставрополе.\n\n"
        "Их лёгкий, летний данс-поп предвосхитил звучание, которое станет "
        "мейнстримом уже в следующем десятилетии.\n\n"
        "Группа стала своеобразным мостом между строгой рок-сценой 90-х "
        "и более расслабленной поп-эстетикой 2000-х. 🎶",
        "Гости из будущего Останусь"
    ),
    (
        "🥁 *Мастер и тяжёлый рок вопреки всему*\n\n"
        "Пока поп-сцена набирала обороты, группа Мастер во главе с Черным Обелиском "
        "продолжала держать знамя классического хэви-метала в России.\n\n"
        "Их концерты собирали преданную аудиторию несмотря на почти полное "
        "отсутствие ротации на радио и телевидении.\n\n"
        "Такие группы доказывали, что даже в эпоху поп-бума в России "
        "оставалось место для тяжёлой, бескомпромиссной музыки. 🥁",
        "Черный Обелиск Кто ты"
    ),
    (
        "🎙️ *Валерий Меладзе и баллады, покорившие всю страну*\n\n"
        "Дебютный альбом 'Наступает ночь' 1994 года мгновенно сделал Меладзе "
        "одним из главных исполнителей романтических баллад десятилетия.\n\n"
        "Песня 'Свеча' и другие хиты звучали буквально из каждого окна "
        "и на каждой свадьбе того времени.\n\n"
        "Меладзе одним из первых в России начал системно работать над "
        "качеством студийной записи, приближая её к западным стандартам. 🎙️",
        "Валерий Меладзе Свеча"
    ),
    (
        "🎼 *Танцы Минус и меланхоличная электроника*\n\n"
        "Группа Вячеслава Петкуна появилась в 1996 году и сразу выделилась "
        "нетипичным для российской сцены холодным, атмосферным звучанием.\n\n"
        "Их музыка находилась где-то на стыке брит-попа и электроники — "
        "непривычная смесь для аудитории, привыкшей к гитарному року или чистой попсе.\n\n"
        "Группа заложила основу для целого направления российской альтернативной "
        "сцены, расцветшего уже в 2000-х. 🎼",
        "Танцы Минус Половинка"
    ),
]

# ─── Состояния ────────────────────────────────────────────────────────────────

BIRTH_DATE, BIRTH_YEAR, SEARCH_ARTIST, GUESS_ANSWER, SEARCH_TRACK = range(5)

# ─── База данных ──────────────────────────────────────────────────────────────

def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            birth_year INTEGER,
            joined_at TEXT,
            is_premium INTEGER DEFAULT 0,
            plays INTEGER DEFAULT 0,
            referred_by INTEGER,
            last_active_date TEXT,
            streak_days INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            track_name TEXT NOT NULL,
            artist TEXT NOT NULL,
            year INTEGER,
            yt_link TEXT,
            preview_url TEXT,
            cover_url TEXT,
            added_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS votes (
            user_id INTEGER NOT NULL,
            track_key TEXT NOT NULL,
            vote INTEGER NOT NULL,
            PRIMARY KEY (user_id, track_key)
        );
        CREATE TABLE IF NOT EXISTS game_scores (
            user_id INTEGER PRIMARY KEY,
            correct INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS listens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            track_key TEXT NOT NULL,
            listened_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS shown_facts (
            user_id INTEGER NOT NULL,
            fact_index INTEGER NOT NULL,
            PRIMARY KEY (user_id, fact_index)
        );
    """)
    conn.commit()
    # Миграция: добавляем новые колонки, если база уже существовала без них
    existing_cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    for col, col_def in [
        ("last_active_date", "TEXT"),
        ("streak_days", "INTEGER DEFAULT 0"),
        ("best_streak", "INTEGER DEFAULT 0"),
    ]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")
    conn.commit()
    conn.close()


def register_user(user_id: int, username: str, first_name: str, referred_by: int = None) -> bool:
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (user_id, username, first_name, joined_at, referred_by) VALUES (?, ?, ?, ?, ?)",
            (user_id, username or "", first_name or "", datetime.now().strftime("%d.%m.%Y %H:%M"), referred_by)
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def update_streak(user_id: int) -> dict:
    """Updates the user's daily streak. Call once per /start or main-menu visit.
    Returns dict with keys: streak_days, best_streak, is_new_today, milestone (bool)."""
    today = datetime.now().date()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT last_active_date, streak_days, best_streak FROM users WHERE user_id=?", (user_id,)
    ).fetchone()

    if not row:
        conn.close()
        return {"streak_days": 0, "best_streak": 0, "is_new_today": False, "milestone": False}

    last_active_str, streak_days, best_streak = row
    streak_days = streak_days or 0
    best_streak = best_streak or 0

    is_new_today = True
    if last_active_str:
        try:
            last_active = datetime.strptime(last_active_str, "%Y-%m-%d").date()
        except ValueError:
            last_active = None
        if last_active == today:
            is_new_today = False
        elif last_active == today - timedelta(days=1):
            streak_days += 1
        else:
            streak_days = 1
    else:
        streak_days = 1

    if is_new_today:
        best_streak = max(best_streak, streak_days)
        conn.execute(
            "UPDATE users SET last_active_date=?, streak_days=?, best_streak=? WHERE user_id=?",
            (today.strftime("%Y-%m-%d"), streak_days, best_streak, user_id)
        )
        conn.commit()

    conn.close()
    milestone = is_new_today and streak_days in (3, 7, 14, 30, 60, 100)
    return {"streak_days": streak_days, "best_streak": best_streak,
            "is_new_today": is_new_today, "milestone": milestone}


def get_inactive_users(days: int = 7) -> list:
    """Returns (user_id, first_name, streak_days) for users inactive for `days`+ days."""
    cutoff = (datetime.now().date() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT user_id, first_name, streak_days FROM users "
        "WHERE last_active_date IS NOT NULL AND last_active_date < ?", (cutoff,)
    ).fetchall()
    conn.close()
    return rows


def save_birth_year(user_id: int, year: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET birth_year=? WHERE user_id=?", (year, user_id))
    conn.commit()
    conn.close()


def get_birth_year(user_id: int) -> Optional[int]:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT birth_year FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def is_premium(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT is_premium FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return bool(row and row[0])


def upgrade_premium(user_id: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET is_premium=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_referral_count(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()[0]
    conn.close()
    return count


def add_favorite(user_id: int, track_name: str, artist: str, year: int,
                 yt_link: str, preview_url: str, cover_url: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute(
        "SELECT id FROM favorites WHERE user_id=? AND track_name=? AND artist=?",
        (user_id, track_name, artist)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO favorites (user_id, track_name, artist, year, yt_link, preview_url, cover_url, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, track_name, artist, year, yt_link, preview_url, cover_url,
             datetime.now().strftime("%d.%m.%Y %H:%M"))
        )
        conn.commit()
    conn.close()


def get_favorites(user_id: int) -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, track_name, artist, year, yt_link FROM favorites WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


def remove_favorite(fav_id: int, user_id: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM favorites WHERE id=? AND user_id=?", (fav_id, user_id))
    conn.commit()
    conn.close()


def update_game_score(user_id: int, correct: bool) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO game_scores (user_id, correct, total) VALUES (?, ?, 1) "
        "ON CONFLICT(user_id) DO UPDATE SET correct=correct+?, total=total+1",
        (user_id, 1 if correct else 0, 1 if correct else 0)
    )
    conn.commit()
    conn.close()


def get_game_score(user_id: int) -> tuple:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT correct, total FROM game_scores WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row if row else (0, 0)


def log_listen(user_id: int, track_key: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO listens (user_id, track_key, listened_at) VALUES (?, ?, ?)",
        (user_id, track_key, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.execute("UPDATE users SET plays=plays+1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_liked_artists(user_id: int) -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT artist FROM favorites WHERE user_id=? GROUP BY artist ORDER BY COUNT(*) DESC LIMIT 5",
        (user_id,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    plays = conn.execute("SELECT SUM(plays) FROM users").fetchone()[0] or 0
    favs = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
    premium = conn.execute("SELECT COUNT(*) FROM users WHERE is_premium=1").fetchone()[0]
    conn.close()
    return {"users": users, "plays": plays, "favs": favs, "premium": premium}


def get_unseen_fact(user_id: int) -> tuple:
    conn = sqlite3.connect(DB_PATH)
    shown = [r[0] for r in conn.execute(
        "SELECT fact_index FROM shown_facts WHERE user_id=?", (user_id,)
    ).fetchall()]
    all_indices = list(range(len(FACTS_90S)))
    unseen = [i for i in all_indices if i not in shown]
    if not unseen:
        conn.execute("DELETE FROM shown_facts WHERE user_id=?", (user_id,))
        conn.commit()
        unseen = all_indices
    idx = random.choice(unseen)
    conn.execute("INSERT OR IGNORE INTO shown_facts (user_id, fact_index) VALUES (?, ?)", (user_id, idx))
    conn.commit()
    conn.close()
    return idx, FACTS_90S[idx]


def get_all_users() -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [r[0] for r in rows]


# ─── Deezer API ───────────────────────────────────────────────────────────────

def yt_link(query: str) -> str:
    return f"https://music.youtube.com/search?q={urllib.parse.quote(query)}"


_SUSPICIOUS_TITLE_MARKERS = [
    "remix", "radio show", "radio mix", "hosted by", "podcast",
    "mixed)", "mix)", "megamix", "continuous mix", "dj mix",
    "live at", "session", "tribute", "karaoke", "cover version",
]


def _is_clean_track_result(track: dict, query: str) -> bool:
    """Reject results that look like remixes, radio shows, DJ sets, etc.,
    unless the original query itself explicitly asked for one of those."""
    title = (track.get("title") or "").lower()
    query_lower = query.lower()
    for marker in _SUSPICIOUS_TITLE_MARKERS:
        if marker in title and marker not in query_lower:
            return False
    return True


async def deezer_search(query: str, limit: int = 1) -> Optional[dict]:
    try:
        async with httpx.AsyncClient() as c:
            # Берём больше кандидатов, чтобы было из чего выбирать чистый результат
            r = await c.get("https://api.deezer.com/search",
                             params={"q": query, "limit": max(limit, 8)}, timeout=10)
            data = r.json().get("data", [])
        if not data:
            return None
        # Сначала ищем "чистый" результат (не ремикс/не радио-шоу/не DJ-сет)
        for track in data:
            if _is_clean_track_result(track, query):
                return track
        # Если все результаты подозрительные — возвращаем первый как раньше
        # (лучше показать хоть что-то похожее, чем ничего)
        return data[0]
    except Exception as e:
        logger.warning(f"Deezer: {e}")
        return None


def _artist_matches(result_artist: str, wanted_artist: str) -> bool:
    """Loose check that the returned track's artist is actually who we asked for
    (not the original artist showing up because the search matched on song title)."""
    result_norm = result_artist.lower().replace("ё", "е").strip()
    wanted_norm = wanted_artist.lower().replace("ё", "е").strip()
    # Берём первое "весомое" слово из имени исполнителя, которого просили
    # (например, "Дима Билан" -> "билан", "Bad Wolves" -> "bad")
    wanted_key_words = [w for w in wanted_norm.split() if len(w) > 2]
    if not wanted_key_words:
        return wanted_norm in result_norm
    return any(w in result_norm for w in wanted_key_words)


async def deezer_search_verified_artist(artist: str, title: str) -> tuple:
    """Search for a specific artist's version of a track. Prefers a verified
    match by artist name, but falls back to the best text-search result so a
    picture/preview is (almost) always available rather than nothing at all.
    Returns (track_or_None, is_verified: bool)."""
    try:
        async with httpx.AsyncClient() as c:
            # Сначала пробуем точный структурированный запрос Deezer
            r = await c.get(
                "https://api.deezer.com/search",
                params={"q": f'artist:"{artist}" track:"{title}"', "limit": 5},
                timeout=10,
            )
            data = r.json().get("data", [])
            for track in data:
                track_artist = track.get("artist", {}).get("name", "")
                if _artist_matches(track_artist, artist):
                    return track, True

            # Более широкий текстовый поиск
            r = await c.get(
                "https://api.deezer.com/search",
                params={"q": f"{artist} {title}", "limit": 10},
                timeout=10,
            )
            data = r.json().get("data", [])
            for track in data:
                track_artist = track.get("artist", {}).get("name", "")
                if _artist_matches(track_artist, artist):
                    return track, True
            # Ни один результат не подтвердил исполнителя по имени (например,
            # из-за транслитерации в базе Deezer) — берём лучший найденный
            # результат, чтобы у пользователя хотя бы была картинка/превью,
            # а не пустое сообщение, но помечаем как неподтверждённый.
            if data:
                return data[0], False
        return None, False
    except Exception as e:
        logger.warning(f"Deezer verified search: {e}")
        return None, False


async def deezer_search_many(query: str, limit: int = 5) -> list:
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get("https://api.deezer.com/search", params={"q": query, "limit": limit}, timeout=10)
            return r.json().get("data", [])
    except Exception as e:
        logger.warning(f"Deezer: {e}")
        return []


async def deezer_artist_top(artist: str, limit: int = 5) -> list:
    """Top tracks by artist via Deezer."""
    try:
        async with httpx.AsyncClient() as c:
            # Сначала находим artist_id
            r = await c.get("https://api.deezer.com/search/artist", params={"q": artist, "limit": 1}, timeout=10)
            artists = r.json().get("data", [])
            if not artists:
                return await deezer_search_many(artist, limit)
            artist_id = artists[0]["id"]
            r2 = await c.get(f"https://api.deezer.com/artist/{artist_id}/top", params={"limit": limit}, timeout=10)
            return r2.json().get("data", [])
    except Exception as e:
        logger.warning(f"Deezer artist top: {e}")
        return []


async def lastfm_similar(artist: str, track: str) -> list:
    """Get similar tracks via Last.fm."""
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(
                "https://ws.audioscrobbler.com/2.0/",
                params={"method": "track.getSimilar", "artist": artist, "track": track,
                        "api_key": LASTFM_API_KEY, "format": "json", "limit": 3},
                timeout=10
            )
            return r.json().get("similartracks", {}).get("track", [])
    except Exception as e:
        logger.warning(f"LastFM similar: {e}")
        return []


# ─── Карточка трека ───────────────────────────────────────────────────────────

async def send_track_card(update: Update, track: dict, label: str = "",
                           year: Optional[int] = None, context_fact: str = "",
                           show_similar: bool = False) -> None:
    name = track.get("title", "")
    artist = track.get("artist", {}).get("name", "")
    cover = track.get("album", {}).get("cover_big") or track.get("album", {}).get("cover_medium", "")
    preview_url = track.get("preview", "")
    link = yt_link(f"{artist} {name}")
    track_key = f"{artist}::{name}"

    year_str = f" ({year})" if year else ""
    label_str = f"*{label}*\n" if label else ""
    fact_str = f"\n\n📅 _{context_fact}_" if context_fact else ""

    caption = (
        f"{label_str}"
        f"🎵 *{name}*{year_str}\n"
        f"👤 {artist}"
        f"{fact_str}\n\n"
        f"[Слушать на YouTube Music]({link})"
    )

    buttons = [
        InlineKeyboardButton("👍", callback_data="vote_up"),
        InlineKeyboardButton("👎", callback_data="vote_down"),
        InlineKeyboardButton("⭐", callback_data=f"fav::{name[:12]}::{artist[:12]}::{year or 0}"),
    ]
    keyboard_rows = [buttons]
    if show_similar:
        keyboard_rows.append([
            InlineKeyboardButton("🔀 Похожие треки", callback_data=f"similar::{artist}::{name}")
        ])

    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg:
        return

    try:
        if cover:
            await msg.reply_photo(photo=cover, caption=caption, parse_mode="Markdown")
        else:
            await msg.reply_text(caption, parse_mode="Markdown", disable_web_page_preview=True)
        if preview_url:
            await msg.reply_audio(
                audio=preview_url, title=name, performer=artist,
                caption="🎧 Превью 30 сек",
                reply_markup=InlineKeyboardMarkup(keyboard_rows),
            )
        else:
            await msg.reply_text("Оцените:", reply_markup=InlineKeyboardMarkup(keyboard_rows))
    except Exception as e:
        logger.warning(f"send_track_card: {e}")
        try:
            await msg.reply_text(caption, parse_mode="Markdown",
                                 disable_web_page_preview=True,
                                 reply_markup=InlineKeyboardMarkup(keyboard_rows))
        except Exception as e2:
            # Даже запасной вариант не прошёл (например, снова слишком длинный callback_data) —
            # отправляем совсем без кнопок, лишь бы не терять весь ответ пользователю
            logger.warning(f"send_track_card fallback: {e2}")
            await msg.reply_text(caption, parse_mode="Markdown", disable_web_page_preview=True)

    if update.effective_user:
        log_listen(update.effective_user.id, track_key)


# ─── Главное меню ─────────────────────────────────────────────────────────────

def main_menu_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    premium = is_premium(user_id) if user_id else False
    premium_btn = "💎 Premium (активен)" if premium else "💎 Получить Premium"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕰️ Ностальгия", callback_data="cat_nostalgia")],
        [InlineKeyboardButton("🎸 Музыка", callback_data="cat_music")],
        [InlineKeyboardButton("🎤 90-е сегодня", callback_data="cat_covers")],
        [InlineKeyboardButton("🔍 Поиск", callback_data="cat_search")],
        [InlineKeyboardButton("🎮 Игра и профиль", callback_data="cat_profile")],
        [InlineKeyboardButton(premium_btn, callback_data="premium_info")],
        [InlineKeyboardButton("💌 Канал Елены про музыку и не только", url="https://t.me/elena_music90s")],
    ])


def nostalgia_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ Машина времени", callback_data="time_machine")],
        [InlineKeyboardButton("🎒 Детство", callback_data="childhood")],
        [InlineKeyboardButton("📻 Радио года", callback_data="radio_year")],
        [InlineKeyboardButton("🎵 Факт дня", callback_data="daily_fact")],
        [InlineKeyboardButton("◀ Главное меню", callback_data="main_menu")],
    ])


def music_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎸 Жанры", callback_data="genres")],
        [InlineKeyboardButton("🎬 Плейлисты", callback_data="themed")],
        [InlineKeyboardButton("🏆 Чарты", callback_data="charts")],
        [InlineKeyboardButton("🎭 Настроение дня", callback_data="mood")],
        [InlineKeyboardButton("◀ Главное меню", callback_data="main_menu")],
    ])


def search_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Поиск артиста", callback_data="search_artist")],
        [InlineKeyboardButton("🎵 Поиск трека", callback_data="search_track")],
        [InlineKeyboardButton("◀ Главное меню", callback_data="main_menu")],
    ])


def profile_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Угадай год", callback_data="game_start")],
        [InlineKeyboardButton("⭐ Избранное", callback_data="show_favorites")],
        [InlineKeyboardButton("🔥 Моя серия", callback_data="show_streak")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton("👥 Пригласить друга", callback_data="referral")],
        [InlineKeyboardButton("◀ Главное меню", callback_data="main_menu")],
    ])


# ─── 90-е сегодня: оригинал vs современный кавер ──────────────────────────────

COVERS_90S = [
    ("Крылья", "Наутилус Помпилиус", "Крылья", "Наутилус Помпилиус Крылья",
     "ZOLOTO", "ZOLOTO Крылья"),
    ("Группа крови", "Кино (Виктор Цой)", "Группа крови", "Кино Группа крови",
     "Чичерина", "Чичерина Группа крови"),
    ("Звезда по имени Солнце", "Кино (Виктор Цой)", "Звезда по имени Солнце", "Кино Звезда по имени Солнце",
     "Би-2", "Би-2 Звезда по имени Солнце"),
    ("Zombie", "The Cranberries", "Zombie", "The Cranberries Zombie",
     "Bad Wolves", "Bad Wolves Zombie"),
    ("Wonderwall", "Oasis", "Wonderwall", "Oasis Wonderwall",
     "Ryan Adams", "Ryan Adams Wonderwall"),
    ("Creep", "Radiohead", "Creep", "Radiohead Creep",
     "Scala & Kolacny Brothers", "Scala Kolacny Brothers Creep"),
    ("No Diggity", "Blackstreet", "No Diggity", "Blackstreet No Diggity",
     "Chet Faker", "Chet Faker No Diggity"),
    ("My Heart Will Go On", "Céline Dion", "My Heart Will Go On", "Celine Dion My Heart Will Go On",
     "2CELLOS", "2CELLOS My Heart Will Go On"),
    ("Nothing Compares 2 U", "Sinéad O'Connor", "Nothing Compares 2 U", "Sinead OConnor Nothing Compares 2 U",
     "Chris Cornell", "Chris Cornell Nothing Compares 2 U"),
    ("Losing My Religion", "R.E.M.", "Losing My Religion", "REM Losing My Religion",
     "Postmodern Jukebox", "Postmodern Jukebox Losing My Religion"),
    ("Barbie Girl", "Aqua", "Barbie Girl", "Aqua Barbie Girl",
     "Kim Petras", "Kim Petras Barbie Girl"),
    ("Personal Jesus", "Depeche Mode", "Personal Jesus", "Depeche Mode Personal Jesus",
     "Johnny Cash", "Johnny Cash Personal Jesus"),
    ("Enjoy the Silence", "Depeche Mode", "Enjoy the Silence", "Depeche Mode Enjoy the Silence",
     "Tori Amos", "Tori Amos Enjoy the Silence"),
    ("Basket Case", "Green Day", "Basket Case", "Green Day Basket Case",
     "Boyce Avenue", "Boyce Avenue Basket Case"),
    ("I Want It That Way", "Backstreet Boys", "I Want It That Way", "Backstreet Boys I Want It That Way",
     "Boyce Avenue", "Boyce Avenue I Want It That Way"),
    ("Don't Speak", "No Doubt", "Don't Speak", "No Doubt Dont Speak",
     "Boyce Avenue", "Boyce Avenue Dont Speak"),
    ("All Star", "Smash Mouth", "All Star", "Smash Mouth All Star",
     "Me First and the Gimme Gimmes", "Me First and the Gimme Gimmes All Star"),
    ("Кукушка", "Кино (Виктор Цой)", "Кукушка", "Кино Кукушка",
     "Полина Гагарина", "Полина Гагарина Кукушка"),
]


def covers_menu_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for i, (display_title, display_artist, *_rest) in enumerate(COVERS_90S):
        rows.append([InlineKeyboardButton(f"{display_title} — {display_artist}", callback_data=f"cover_{i}")])
    rows.append([InlineKeyboardButton("◀ Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)


async def send_fact_track(update: Update, track: dict) -> None:
    """Отправляет трек в разделе фактов: полная карточка + кнопка YouTube"""
    name = track.get("title", "")
    artist = track.get("artist", {}).get("name", "")
    cover = track.get("album", {}).get("cover_big") or track.get("album", {}).get("cover_medium", "")
    preview_url = track.get("preview", "")
    link = yt_link(f"{artist} {name}")
    track_key = f"{artist}::{name}"
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg:
        return
    caption = f"🎵 *Послушай трек из этой истории*\n\n🎵 *{name}*\n👤 {artist}"
    # Отправляем обложку отдельно (если не удастся — не страшно)
    if cover:
        try:
            await msg.reply_photo(photo=cover, caption=caption, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"send_fact_track photo: {e}")
            try:
                await msg.reply_text(caption, parse_mode="Markdown")
            except Exception:
                pass
    else:
        try:
            await msg.reply_text(caption, parse_mode="Markdown")
        except Exception:
            pass
    # Превью и кнопка YouTube — отправляем всегда отдельно
    if preview_url:
        try:
            await msg.reply_audio(
                audio=preview_url,
                title=name,
                performer=artist,
                caption="🎧 Превью 30 сек",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👍", callback_data="vote_up"),
                     InlineKeyboardButton("👎", callback_data="vote_down")],
                    [InlineKeyboardButton("▶️ Слушать полностью на YouTube", url=link)],
                ])
            )
        except Exception as e:
            logger.warning(f"send_fact_track audio: {e}")
    elif link:
        # Если нет превью — хотя бы кнопка YouTube
        try:
            await msg.reply_text(
                "▶️ Послушай полностью:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("▶️ Слушать на YouTube", url=link)],
                ])
            )
        except Exception as e:
            logger.warning(f"send_fact_track yt_button: {e}")


async def send_main_menu(msg, user_id: int, text: str = "Выбери раздел:") -> None:
    await msg.reply_text(
        f"🕰️ *Музыкальный сервис 90-х*\n\n{text}",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(user_id),
    )


# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    args = context.args or []

    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0].split("_")[1])
        except (IndexError, ValueError):
            pass

    is_new = register_user(user.id, user.username, user.first_name, referred_by)

    if is_new and referred_by:
        ref_count = get_referral_count(referred_by)
        if ref_count >= 5:
            upgrade_premium(referred_by)
            try:
                await context.bot.send_message(
                    chat_id=referred_by,
                    text="🎉 Ты пригласил 5 друзей и получил *Premium* навсегда! 💎",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    premium_badge = " 💎" if is_premium(user.id) else ""
    streak = update_streak(user.id)

    greeting = (
        f"👋 Привет, {user.first_name}! Я бот о музыке 80-х и 90-х 🎵\n\n"
        "Вот что я умею:\n\n"
        "⏰ *Машина времени* — введи дату рождения и узнай, какие хиты звучали в твоё детство\n"
        "🎸 *Жанры* — слушай треки и историю каждого музыкального стиля эпохи\n"
        "🎮 *Угадай год* — мини-игра: слушаешь 30 сек и угадываешь год выхода трека\n"
        "📅 *Факт дня* — интересные истории о музыке и событиях тех лет\n"
        "🔍 *Поиск* — найди любого артиста и послушай его треки\n"
        "🎬 *Плейлисты* — подборки под настроение: вечеринка, романтика, дорога...\n\n"
        "А ещё у меня, Елены, есть канал, где пишу про музыку и всё, что цепляет за душу 💌 "
        "(ссылка внизу меню)\n\n"
        "Просто нажми кнопку ниже 👇"
        if is_new else
        f"🎵 С возвращением, {user.first_name}{premium_badge}!\n\nВыбери раздел:"
    )

    if not is_new and streak["is_new_today"] and streak["streak_days"] >= 2:
        streak_line = f"\n\n🔥 Серия захода: *{streak['streak_days']} {_days_word(streak['streak_days'])} подряд!*"
        if streak["milestone"]:
            streak_line += f"\n🏆 Новый рубеж! Так держать — ты в топе самых верных слушателей 90-х."
        greeting += streak_line

    await update.message.reply_text(
        greeting,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(user.id),
    )
    return ConversationHandler.END


def _days_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return "дня"
    return "дней"


# ─── Машина времени ───────────────────────────────────────────────────────────

async def handle_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        birth = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("❌ Формат: *ДД.ММ.ГГГГ* — например 15.03.1985", parse_mode="Markdown")
        return BIRTH_DATE

    birth_year = birth.year
    save_birth_year(update.effective_user.id, birth_year)
    await update.message.reply_text("⏳ Запускаю машину времени...")

    milestones = [(age, birth_year + age) for age in [5, 8, 10, 16, 18] if 1984 <= birth_year + age <= 1999]

    if not milestones:
        await update.message.reply_text(
            "🕰️ Твоё взросление прошло вне 80-х и 90-х — но эта музыка всё равно твоя!\n\nВот лучшие хиты эпохи:",
        )
        milestones = [(0, random.randint(1984, 1999))]

    for age, year in milestones:
        facts = HISTORY.get(year, [])
        fact = random.choice(facts) if facts else ""
        age_text = f"Тебе было *{age} лет* — " if age > 0 else ""

        await update.message.reply_text(
            f"🎂 {age_text}на дворе *{year} год*\n{'📅 _' + fact + '_' if fact else ''}",
            parse_mode="Markdown",
        )

        # Показываем хиты того года со ссылками
        hits = YEAR_HITS.get(year, [])
        if hits:
            hits_text = f"🎵 *Хиты {year} года:*\n\n"
            for artist, song, link in hits:
                hits_text += f"• [{song} — {artist}]({link})\n"
            await update.message.reply_text(
                hits_text,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

        # Отправляем превью первого трека
        genre = random.choice(list(GENRES.values()))
        artist = random.choice(genre["artists"])
        track = await deezer_search(artist) or await deezer_search(f"hits {year}")
        if track:
            await send_track_card(update, track, label=f"🎵 Хит {year} года", year=year,
                                   context_fact=fact, show_similar=True)

    await send_main_menu(update.message, update.effective_user.id, "Что дальше?")
    return ConversationHandler.END


# ─── Саундтрек детства ────────────────────────────────────────────────────────

async def handle_birth_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        birth_year = int(text)
        if birth_year < 1950 or birth_year > 2005:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введи год числом, например *1982*", parse_mode="Markdown")
        return BIRTH_YEAR

    save_birth_year(update.effective_user.id, birth_year)
    teen_years = [y for y in range(birth_year + 10, birth_year + 19) if 1990 <= y <= 1999]

    if not teen_years:
        await send_main_menu(update.message, update.effective_user.id,
                             "Твоё детство вне 90-х, но эпоха всё равно легендарна!")
        return ConversationHandler.END

    await update.message.reply_text(
        f"🎒 Твои главные годы: *{teen_years[0]}–{teen_years[-1]}*\n\nСоставляю саундтрек...",
        parse_mode="Markdown",
    )

    genres_list = list(GENRES.values())
    random.shuffle(genres_list)

    for i, year in enumerate(teen_years[:4]):
        facts = HISTORY.get(year, [])
        fact = random.choice(facts) if facts else ""
        genre = genres_list[i % len(genres_list)]
        artist = random.choice(genre["artists"])
        track = await deezer_search(artist) or await deezer_search(f"{genre['query']}")
        if track:
            await send_track_card(update, track,
                                   label=f"{genre['color']} {year} — {genre['name']}",
                                   year=year, context_fact=fact, show_similar=True)

    await send_main_menu(update.message, update.effective_user.id, "Добавляй в избранное ⭐")
    return ConversationHandler.END


# ─── Поиск по артисту ─────────────────────────────────────────────────────────

async def handle_search_artist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    artist = update.message.text.strip()
    await update.message.reply_text(f"🔍 Ищу треки: *{artist}*...", parse_mode="Markdown")

    tracks = await deezer_artist_top(artist, limit=5)
    if not tracks:
        tracks = await deezer_search_many(artist, limit=5)

    if not tracks:
        await update.message.reply_text(
            f"😕 Не нашёл *{artist}* в базе.\n\nПроверь написание или попробуй на английском.",
            parse_mode="Markdown",
        )
        await send_main_menu(update.message, update.effective_user.id)
        return ConversationHandler.END

    await update.message.reply_text(f"🎵 Топ треков *{artist}*:", parse_mode="Markdown")
    for track in tracks[:4]:
        await send_track_card(update, track, show_similar=True)

    await send_main_menu(update.message, update.effective_user.id)
    return ConversationHandler.END


# ─── Поиск по треку ───────────────────────────────────────────────────────────

async def handle_search_track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query_text = update.message.text.strip()
    await update.message.reply_text(f"🔍 Ищу трек: *{query_text}*...", parse_mode="Markdown")

    track = await deezer_search(query_text)
    if not track:
        await update.message.reply_text(
            f"😕 Не нашёл трек *{query_text}*.\n\n"
            "Попробуй написать *Артист — Название* или на английском.",
            parse_mode="Markdown",
        )
        await send_main_menu(update.message, update.effective_user.id)
        return ConversationHandler.END

    await send_track_card(update, track, label="🎵 Нашёл трек", show_similar=True)
    await send_main_menu(update.message, update.effective_user.id)
    return ConversationHandler.END


# ─── Радио года ───────────────────────────────────────────────────────────────

async def play_radio_year(msg, update: Update, year: int) -> None:
    await msg.reply_text(f"📻 Включаю *{year} год*...", parse_mode="Markdown")

    facts = HISTORY.get(year, [])
    if facts:
        await msg.reply_text(
            f"📅 *{year} год — события:*\n\n" + "\n".join(f"• {f}" for f in facts),
            parse_mode="Markdown",
        )

    genres_list = list(GENRES.values())
    random.shuffle(genres_list)
    for genre in genres_list[:3]:
        artist = random.choice(genre["artists"])
        track = await deezer_search(artist) or await deezer_search(genre["query"])
        if track:
            await send_track_card(update, track, label=f"{genre['color']} {genre['name']}", year=year,
                                   show_similar=True)

    await send_main_menu(msg, update.effective_user.id, f"Это был *{year}*!")


# ─── Жанры ────────────────────────────────────────────────────────────────────

async def play_genre(update: Update, genre_key: str) -> None:
    query = update.callback_query
    genre = GENRES.get(genre_key)
    if not genre:
        return

    # История жанра
    await query.message.reply_text(
        genre.get("history", f"{genre['color']} *{genre['name']}*\n_{genre['desc']}_"),
        parse_mode="Markdown",
    )

    # Топ альбомы со ссылками
    albums = genre.get("albums", [])
    if albums:
        albums_text = f"💿 *Легендарные альбомы:*\n\n"
        for artist, album, link in albums:
            albums_text += f"• [{album} — {artist}]({link})\n"
        await query.message.reply_text(
            albums_text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    # Треки с превью
    await query.message.reply_text(f"🎵 *Слушай прямо сейчас:*", parse_mode="Markdown")
    for artist in random.sample(genre["artists"], min(3, len(genre["artists"]))):
        track = await deezer_search(artist)
        if track:
            await send_track_card(update, track, label=f"{genre['color']} {genre['name']}", show_similar=True)

    await send_main_menu(query.message, update.effective_user.id)


# ─── Тематические плейлисты ───────────────────────────────────────────────────

async def cmd_themed(update: Update) -> None:
    msg = update.message or update.callback_query.message
    buttons = [
        [InlineKeyboardButton(pl["name"], callback_data=f"themed_{key}")]
        for key, pl in THEMED_PLAYLISTS.items()
    ]
    buttons.append([InlineKeyboardButton("🏠 Меню", callback_data="main_menu")])
    await msg.reply_text(
        "🎬 *Тематические плейлисты*\n\nВыбери настроение:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def play_themed(update: Update, key: str) -> None:
    query = update.callback_query
    pl = THEMED_PLAYLISTS.get(key)
    if not pl:
        return

    await query.message.reply_text(f"{pl['name']}\n\nЗагружаю...", parse_mode="Markdown")

    for artist in random.sample(pl["artists"], min(4, len(pl["artists"]))):
        track = await deezer_search(artist)
        if track:
            await send_track_card(update, track, label=pl["name"], show_similar=True)

    await send_main_menu(query.message, update.effective_user.id)


# ─── Топ чарты ────────────────────────────────────────────────────────────────

async def cmd_charts(update: Update) -> None:
    msg = update.message or update.callback_query.message
    buttons = [
        [InlineKeyboardButton(f"🏆 {y}", callback_data=f"chart_{y}") for y in range(1990, 1995)],
        [InlineKeyboardButton(f"🏆 {y}", callback_data=f"chart_{y}") for y in range(1995, 2000)],
        [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")],
    ]
    await msg.reply_text(
        "🏆 *Топ чарты 90-х*\n\nВыбери год — покажу реальные хиты Billboard:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def play_chart(update: Update, year: int) -> None:
    query = update.callback_query
    chart = TOP_CHARTS.get(year, [])

    text = f"🏆 *Топ хиты {year} года:*\n\n"
    for i, song in enumerate(chart, 1):
        text += f"{i}. {song}\n"

    await query.message.reply_text(text, parse_mode="Markdown")

    # Играем первые 2 трека
    for song in chart[:2]:
        parts = song.split(" - ", 1)
        if len(parts) == 2:
            track = await deezer_search(f"{parts[0]} {parts[1]}")
            if track:
                await send_track_card(update, track, label=f"🏆 Хит {year}", year=year, show_similar=True)

    await send_main_menu(query.message, update.effective_user.id)


# ─── Похожие треки ────────────────────────────────────────────────────────────

async def play_similar(update: Update, artist: str, track_name: str) -> None:
    query = update.callback_query
    await query.message.reply_text(f"🔀 Ищу похожие на *{track_name}*...", parse_mode="Markdown")

    similar = await lastfm_similar(artist, track_name)

    found = 0
    for s in similar[:3]:
        s_artist = s.get("artist", {}).get("name", "") if isinstance(s.get("artist"), dict) else s.get("artist", "")
        s_name = s.get("name", "")
        track = await deezer_search(f"{s_artist} {s_name}")
        if track:
            await send_track_card(update, track, label="🔀 Похожий трек", show_similar=True)
            found += 1

    if found == 0:
        # Fallback: ищем другие треки того же артиста
        tracks = await deezer_artist_top(artist, limit=5)
        for t in tracks[:2]:
            if t.get("title", "").lower() != track_name.lower():
                await send_track_card(update, t, label=f"🎵 Ещё от {artist}", show_similar=True)
                found += 1

    if found == 0:
        await query.message.reply_text("😕 Похожих не нашёл. Попробуй другой трек.")


# ─── Игра: Угадай год ─────────────────────────────────────────────────────────

async def game_round(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.callback_query.message if update.callback_query else update.message
    genre = random.choice(list(GENRES.values()))
    artist = random.choice(genre["artists"])
    correct_year = random.randint(1990, 1999)

    track = await deezer_search(artist)
    if not track:
        await msg.reply_text("Не удалось загрузить трек, попробуй ещё раз.",
                              reply_markup=InlineKeyboardMarkup([[
                                  InlineKeyboardButton("🔄 Ещё раз", callback_data="game_round")
                              ]]))
        return GUESS_ANSWER

    name = track.get("title", "")
    track_artist = track.get("artist", {}).get("name", "")
    preview_url = track.get("preview", "")
    cover = track.get("album", {}).get("cover_big", "")

    context.user_data["game_year"] = correct_year
    context.user_data["game_track"] = f"{name} — {track_artist}"

    wrong = random.sample([y for y in range(1990, 2000) if y != correct_year], 3)
    options = sorted([correct_year] + wrong)
    buttons = [[InlineKeyboardButton(str(y), callback_data=f"guess_{y}")] for y in options]

    if cover:
        await msg.reply_photo(photo=cover,
                               caption=f"🎵 *{name}*\n👤 {track_artist}\n\nВ каком году?",
                               parse_mode="Markdown")
    if preview_url:
        await msg.reply_audio(audio=preview_url, title=name, performer=track_artist,
                               caption="🎧 Слушай и угадывай!")
    await msg.reply_text("📅 Выбери год:", reply_markup=InlineKeyboardMarkup(buttons))
    return GUESS_ANSWER


async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    guessed = int(query.data.split("_")[1])
    correct_year = context.user_data.get("game_year", 0)
    track_name = context.user_data.get("game_track", "")
    user_id = update.effective_user.id

    is_correct = guessed == correct_year
    update_game_score(user_id, is_correct)
    correct, total = get_game_score(user_id)

    history = HISTORY.get(correct_year, [])
    fact = random.choice(history) if history else ""

    result = "✅ *Правильно!*" if is_correct else f"❌ *Нет! Это был {correct_year} год*"
    text = f"{result}\n\n🎵 _{track_name}_\n\n🏆 Счёт: {correct}/{total}"
    if fact:
        text += f"\n\n📅 _{fact}_"

    await query.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Следующий", callback_data="game_round")],
            [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")],
        ])
    )
    return GUESS_ANSWER


# ─── Избранное ────────────────────────────────────────────────────────────────

async def show_favorites(update: Update) -> None:
    user_id = update.effective_user.id
    favs = get_favorites(user_id)
    msg = update.message or update.callback_query.message

    if not favs:
        await msg.reply_text(
            "⭐ Избранное пусто.\n\nНажимай ⭐ под треками чтобы сохранять!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]])
        )
        return

    text = "⭐ *Твоё избранное:*\n\n"
    buttons = []
    for fav_id, track_name, artist, year, yt in favs:
        year_str = f" ({year})" if year else ""
        text += f"🎵 [{track_name} — {artist}{year_str}]({yt})\n"
        buttons.append([InlineKeyboardButton(f"🗑 {track_name[:28]}", callback_data=f"del_fav::{fav_id}")])

    buttons.append([InlineKeyboardButton("🏠 Меню", callback_data="main_menu")])
    await msg.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True,
                          reply_markup=InlineKeyboardMarkup(buttons))


# ─── Premium ──────────────────────────────────────────────────────────────────

async def show_premium_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    msg = update.callback_query.message
    ref_count = get_referral_count(user_id)

    if is_premium(user_id):
        await msg.reply_text(
            "💎 *Premium активен!*\n\n"
            "У тебя есть доступ ко всем функциям:\n"
            "• Расширенные плейлисты\n"
            "• Персональные рекомендации\n"
            "• Приоритетный поиск",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]])
        )
        return

    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    await msg.reply_text(
        f"💎 *Premium подписка*\n\n"
        f"*Что даёт Premium:*\n"
        f"• Расширенные плейлисты (6 треков вместо 3)\n"
        f"• Персональные рекомендации на основе избранного\n"
        f"• Доступ ко всем тематическим плейлистам\n\n"
        f"*Как получить:*\n"
        f"⭐ За {PREMIUM_STARS} Telegram Stars\n"
        f"👥 Пригласи 5 друзей — получи бесплатно (сейчас: {ref_count}/5)\n",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⭐ Купить за {PREMIUM_STARS} Stars", callback_data="buy_premium")],
            [InlineKeyboardButton("👥 Пригласить друзей", url=ref_link)],
            [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")],
        ])
    )


async def handle_buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title="Premium подписка — Музыка 90-х",
        description="Расширенные плейлисты, рекомендации, полный доступ",
        payload="premium_subscription",
        currency="XTR",
        prices=[LabeledPrice("Premium", PREMIUM_STARS)],
    )


async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.pre_checkout_query.answer(ok=True)


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    payload = update.message.successful_payment.invoice_payload
    if payload == "premium_subscription":
        upgrade_premium(user_id)
        await update.message.reply_text(
            "🎉 *Premium активирован!*\n\nДобро пожаловать в клуб 💎",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(user_id),
        )


# ─── Реферальная система ──────────────────────────────────────────────────────

async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    ref_count = get_referral_count(user_id)
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    msg = update.callback_query.message

    await msg.reply_text(
        f"👥 *Пригласи друзей — получи Premium*\n\n"
        f"Твой прогресс: *{ref_count}/5* друзей\n\n"
        f"Поделись ссылкой:\n`{ref_link}`\n\n"
        f"_Каждый кто перейдёт по ссылке засчитывается._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Поделиться", url=f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote('Слушай музыку 90-х!')}")]  ,
            [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")],
        ])
    )


# ─── Персональные рекомендации (для Premium) ──────────────────────────────────

async def personal_recommendations(update: Update, user_id: int) -> None:
    msg = update.callback_query.message if update.callback_query else update.message
    liked_artists = get_liked_artists(user_id)

    if not liked_artists:
        await msg.reply_text("⭐ Добавь треки в избранное — и я сделаю персональные рекомендации!")
        return

    await msg.reply_text(
        f"✨ *Персональные рекомендации*\n\nНа основе твоих {len(liked_artists)} любимых исполнителей:",
        parse_mode="Markdown",
    )

    for artist in liked_artists[:3]:
        tracks = await deezer_artist_top(artist, limit=3)
        for track in tracks[:2]:
            await send_track_card(update, track, label=f"✨ Рекомендация: {artist}", show_similar=True)


# ─── Главный callback обработчик ──────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user

    if data == "main_menu":
        await send_main_menu(query.message, user.id)
        return ConversationHandler.END

    if data == "cat_nostalgia":
        await query.message.reply_text(
            "🕰️ *Ностальгия*\n\nВыбери раздел:", parse_mode="Markdown",
            reply_markup=nostalgia_menu_keyboard(),
        )
        return ConversationHandler.END

    if data == "cat_music":
        await query.message.reply_text(
            "🎸 *Музыка*\n\nВыбери раздел:", parse_mode="Markdown",
            reply_markup=music_menu_keyboard(),
        )
        return ConversationHandler.END

    if data == "cat_covers":
        await query.message.reply_text(
            "🎤 *90-е сегодня*\n\n"
            "Выбери хит 90-х — покажу оригинал и его известный современный кавер:",
            parse_mode="Markdown",
            reply_markup=covers_menu_keyboard(),
        )
        return ConversationHandler.END

    if data.startswith("cover_"):
        idx = int(data.split("_")[1])
        if 0 <= idx < len(COVERS_90S):
            (disp_title, disp_artist, orig_title, orig_query,
             cover_artist, cover_query) = COVERS_90S[idx]
            yt = yt_link(f"{cover_artist} {disp_title}")
            # Пытаемся найти обложку/превью через Deezer как бонус, но не зависим от него
            cover_track, is_verified = await deezer_search_verified_artist(cover_artist, disp_title)
            cover_img = ""
            if cover_track:
                cover_img = (cover_track.get("album", {}).get("cover_big")
                             or cover_track.get("album", {}).get("cover_medium", ""))
            note = "" if is_verified else "\n_(точную версию не нашли в Deezer — точно есть на YouTube)_"
            caption = (
                f"🎤 *{disp_title}* — {cover_artist}\n"
                f"_(оригинал: {disp_artist}, 90-е)_{note}\n\n"
                f"[Слушать на YouTube]({yt})"
            )
            try:
                if cover_img:
                    await query.message.reply_photo(photo=cover_img, caption=caption, parse_mode="Markdown")
                else:
                    await query.message.reply_text(caption, parse_mode="Markdown", disable_web_page_preview=True)
                if cover_track and is_verified and cover_track.get("preview"):
                    await query.message.reply_audio(
                        audio=cover_track["preview"], title=disp_title, performer=cover_artist,
                        caption="🎧 Превью 30 сек",
                    )
            except Exception as e:
                logger.warning(f"cover send: {e}")
                await query.message.reply_text(caption, parse_mode="Markdown", disable_web_page_preview=True)
            await query.message.reply_text(
                "Ещё сравнение?", reply_markup=covers_menu_keyboard(),
            )
        return ConversationHandler.END

    if data == "cat_search":
        await query.message.reply_text(
            "🔍 *Поиск*\n\nВыбери, что искать:", parse_mode="Markdown",
            reply_markup=search_menu_keyboard(),
        )
        return ConversationHandler.END

    if data == "cat_profile":
        await query.message.reply_text(
            "🎮 *Игра и профиль*\n\nВыбери раздел:", parse_mode="Markdown",
            reply_markup=profile_menu_keyboard(),
        )
        return ConversationHandler.END

    if data == "time_machine":
        await query.message.reply_text(
            "⏰ *Машина времени*\n\nВведи дату рождения: *ДД.ММ.ГГГГ*\n_Например: 15.03.1985_",
            parse_mode="Markdown",
        )
        return BIRTH_DATE

    if data == "childhood":
        await query.message.reply_text(
            "🎒 *Саундтрек детства*\n\nВведи год рождения:\n_Например: 1982_",
            parse_mode="Markdown",
        )
        return BIRTH_YEAR

    if data == "mood":
        buttons = [
            [InlineKeyboardButton(MOODS["happy"]["name"], callback_data="mood_happy"),
             InlineKeyboardButton(MOODS["sad"]["name"], callback_data="mood_sad")],
            [InlineKeyboardButton(MOODS["energetic"]["name"], callback_data="mood_energetic"),
             InlineKeyboardButton(MOODS["romantic"]["name"], callback_data="mood_romantic")],
            [InlineKeyboardButton(MOODS["nostalgic"]["name"], callback_data="mood_nostalgic"),
             InlineKeyboardButton(MOODS["chill"]["name"], callback_data="mood_chill")],
            [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")],
        ]
        await query.message.reply_text(
            "🎭 *Настроение дня*\n\nКак ты себя чувствуешь?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return ConversationHandler.END

    if data.startswith("mood_"):
        mood_key = data.split("_", 1)[1]
        mood = MOODS.get(mood_key)
        if mood:
            await query.message.reply_text(
                f"{mood['name']} — составляю плейлист... 🎵",
                parse_mode="Markdown",
            )
            selected = random.sample(mood["tracks"], min(5, len(mood["tracks"])))
            found = 0
            for track_query in selected:
                track = await deezer_search(track_query)
                if track:
                    await send_track_card(update, track, label=f"🎭 {mood['name']}", show_similar=True)
                    found += 1
            if found == 0:
                await query.message.reply_text("😕 Не нашёл треки, попробуй ещё раз.")
        await send_main_menu(query.message, update.effective_user.id)
        return ConversationHandler.END

    if data == "my_stats":
        user_id = update.effective_user.id
        conn = sqlite3.connect(DB_PATH)
        plays = conn.execute("SELECT plays FROM users WHERE user_id=?", (user_id,)).fetchone()
        favs = conn.execute("SELECT COUNT(*) FROM favorites WHERE user_id=?", (user_id,)).fetchone()
        score = conn.execute("SELECT correct, total FROM game_scores WHERE user_id=?", (user_id,)).fetchone()
        shown = conn.execute("SELECT COUNT(*) FROM shown_facts WHERE user_id=?", (user_id,)).fetchone()
        conn.close()
        plays_count = plays[0] if plays else 0
        favs_count = favs[0] if favs else 0
        correct = score[0] if score else 0
        total = score[1] if score else 0
        facts_count = shown[0] if shown else 0
        accuracy = f"{int(correct/total*100)}%" if total > 0 else "—"
        await query.message.reply_text(
            f"📊 *Твоя статистика*\n\n"
            f"▶️ Треков послушано: *{plays_count}*\n"
            f"⭐ В избранном: *{favs_count}*\n"
            f"🎮 Угадай год: *{correct}/{total}* ({accuracy})\n"
            f"📅 Фактов прочитано: *{facts_count}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]]),
        )
        return ConversationHandler.END

    if data == "show_streak":
        user_id = update.effective_user.id
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT streak_days, best_streak FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        conn.close()
        streak_days = (row[0] if row else 0) or 0
        best_streak = (row[1] if row else 0) or 0
        if streak_days >= 2:
            text = (
                f"🔥 *Твоя серия*\n\n"
                f"Ты заходишь в бот *{streak_days} {_days_word(streak_days)} подряд!*\n"
                f"🏆 Лучшая серия: *{best_streak} {_days_word(best_streak)}*\n\n"
                f"Заходи завтра, чтобы не потерять серию 👀"
            )
        else:
            text = (
                "🔥 *Твоя серия*\n\n"
                "Пока серии нет — заходи в бот два дня подряд, и она начнётся!\n\n"
                f"🏆 Лучшая серия за всё время: *{best_streak} {_days_word(best_streak)}*"
            )
        await query.message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]]),
        )
        return ConversationHandler.END

    if data == "search_track":
        await query.message.reply_text(
            "🎵 *Поиск по треку*\n\nНапиши название трека или артист + трек:\n"
            "_Например: Wannabe или Spice Girls Wannabe_",
            parse_mode="Markdown",
        )
        return SEARCH_TRACK

    if data == "search_artist":
        await query.message.reply_text(
            "🔍 *Поиск по артисту*\n\nНапиши имя исполнителя:\n_Например: Nirvana или Кино_",
            parse_mode="Markdown",
        )
        return SEARCH_ARTIST

    if data == "radio_year":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📻 {y}", callback_data=f"radio_{y}") for y in range(1990, 1995)],
            [InlineKeyboardButton(f"📻 {y}", callback_data=f"radio_{y}") for y in range(1995, 2000)],
            [InlineKeyboardButton("🔀 Случайный год", callback_data=f"radio_{random.randint(1990, 1999)}")],
            [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")],
        ])
        await query.message.reply_text(
            "📻 *Радио года*\n\nВыбери год:",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return ConversationHandler.END

    if data.startswith("radio_"):
        year = int(data.split("_")[1])
        await play_radio_year(query.message, update, year)
        return ConversationHandler.END

    if data == "genres":
        buttons = [
            [InlineKeyboardButton(f"{g['color']} {g['name']}", callback_data=f"genre_{key}")]
            for key, g in GENRES.items()
        ]
        buttons.append([InlineKeyboardButton("🏠 Меню", callback_data="main_menu")])
        await query.message.reply_text(
            "🎸 *Жанры 90-х:*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return ConversationHandler.END

    if data.startswith("genre_"):
        await play_genre(update, data.split("_", 1)[1])
        return ConversationHandler.END

    if data == "themed":
        await cmd_themed(update)
        return ConversationHandler.END

    if data.startswith("themed_"):
        await play_themed(update, data.split("_", 1)[1])
        return ConversationHandler.END

    if data == "charts":
        await cmd_charts(update)
        return ConversationHandler.END

    if data.startswith("chart_"):
        await play_chart(update, int(data.split("_")[1]))
        return ConversationHandler.END

    if data == "game_start":
        correct, total = get_game_score(user.id)
        score_text = f"Твой счёт: *{correct}/{total}*\n\n" if total > 0 else ""
        await query.message.reply_text(
            f"🎮 *Угадай год!*\n\n{score_text}Я сыграю превью — угадай год выхода!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Поехали!", callback_data="game_round")]])
        )
        return GUESS_ANSWER

    if data == "game_round":
        return await game_round(update, context)

    if data.startswith("guess_"):
        return await handle_guess(update, context)

    if data == "show_favorites":
        await show_favorites(update)
        return ConversationHandler.END

    if data == "daily_fact":
        _, (fact, track_query) = get_unseen_fact(update.effective_user.id)
        await query.message.reply_text(
            f"🎵 *Факт о музыке 90-х*\n\n{fact}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎵 Ещё факт", callback_data="daily_fact")],
                [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")],
            ])
        )
        if track_query:
            track = await deezer_search(track_query)
            if track:
                await send_fact_track(update, track)
        return ConversationHandler.END

    if data == "premium_info":
        await show_premium_info(update, context)
        return ConversationHandler.END

    if data == "buy_premium":
        await handle_buy_premium(update, context)
        return ConversationHandler.END

    if data == "referral":
        await show_referral(update, context)
        return ConversationHandler.END

    if data.startswith("similar::"):
        parts = data.split("::")
        if len(parts) >= 3:
            await play_similar(update, parts[1], parts[2])
        return ConversationHandler.END

    if data.startswith("fav::"):
        parts = data.split("::")
        if len(parts) >= 4:
            track_name = parts[1]
            artist = parts[2]
            year_str = parts[3]
            yt = yt_link(f"{artist} {track_name}")
            preview = ""
            cover = ""
            try:
                year = int(year_str) if year_str and year_str != "0" else None
            except ValueError:
                year = None
            add_favorite(user.id, track_name, artist, year, yt, preview, cover)
            await query.answer("⭐ Добавлено в избранное!", show_alert=False)
        return ConversationHandler.END

    if data.startswith("del_fav::"):
        remove_favorite(int(data.split("::")[1]), user.id)
        await query.message.reply_text("🗑 Удалено из избранного.")
        return ConversationHandler.END

    if data == "vote_up" or data == "vote_down":
        emoji = "👍 Огонь!" if data == "vote_up" else "👎 Понял!"
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(emoji)
        return ConversationHandler.END

    return ConversationHandler.END


# ─── Команды ──────────────────────────────────────────────────────────────────

async def cmd_fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, (fact, track_query) = get_unseen_fact(update.effective_user.id)
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        f"🎵 *Факт о музыке 90-х*\n\n{fact}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎵 Ещё", callback_data="daily_fact")],
            [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")],
        ])
    )
    if track_query:
        track = await deezer_search(track_query)
        if track:
            await send_fact_track(update, track)


async def cmd_favorites_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_favorites(update)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    s = get_stats()
    await update.message.reply_text(
        f"📊 *Статистика Music90s*\n\n"
        f"👥 Пользователей: *{s['users']}*\n"
        f"💎 Premium: *{s['premium']}*\n"
        f"▶️ Воспроизведений: *{s['plays']}*\n"
        f"⭐ В избранном: *{s['favs']}*",
        parse_mode="Markdown",
    )


# ─── Ежедневная рассылка ──────────────────────────────────────────────────────

async def daily_broadcast(bot) -> None:
    users = get_all_users()
    for user_id in users:
        try:
            _, (fact, track_query) = get_unseen_fact(user_id)
            track = await deezer_search(track_query) if track_query else None
            await bot.send_message(
                chat_id=user_id,
                text=f"🎵 *Факт дня о музыке 90-х*\n\n{fact}",
                parse_mode="Markdown",
            )
            if track:
                name = track.get("title", "")
                artist = track.get("artist", {}).get("name", "")
                cover = track.get("album", {}).get("cover_big") or track.get("album", {}).get("cover_medium", "")
                preview_url = track.get("preview", "")
                link = yt_link(f"{artist} {name}")
                track_key = f"{artist}::{name}"
                caption = f"🎵 *{name}*\n👤 {artist}"
                # Обложка
                if cover:
                    try:
                        await bot.send_photo(chat_id=user_id, photo=cover, caption=caption, parse_mode="Markdown")
                    except Exception:
                        try:
                            await bot.send_message(chat_id=user_id, text=caption, parse_mode="Markdown")
                        except Exception:
                            pass
                else:
                    try:
                        await bot.send_message(chat_id=user_id, text=caption, parse_mode="Markdown")
                    except Exception:
                        pass
                # Превью + кнопка YouTube
                if preview_url:
                    try:
                        await bot.send_audio(
                            chat_id=user_id,
                            audio=preview_url,
                            title=name,
                            performer=artist,
                            caption="🎧 Превью 30 сек",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("👍", callback_data="vote_up"),
                                 InlineKeyboardButton("👎", callback_data="vote_down")],
                                [InlineKeyboardButton("▶️ Слушать полностью на YouTube", url=link)],
                            ])
                        )
                    except Exception as e:
                        logger.warning(f"Broadcast audio {user_id}: {e}")
        except Exception as e:
            logger.warning(f"Broadcast {user_id}: {e}")
    return


# ─── Запуск ───────────────────────────────────────────────────────────────────

async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        ("start", "🕰️ Главное меню"),
        ("fact", "🎵 Факт о музыке 90-х"),
        ("favorites", "⭐ Моё избранное"),
        ("stats", "📊 Статистика (админ)"),
    ])
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        daily_broadcast,
        CronTrigger(hour=11, minute=0, timezone="Europe/Moscow"),
        args=[app.bot],
        name="daily_fact",
    )
    scheduler.start()


def main() -> None:
    init_db()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(callback_handler),
        ],
        states={
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_birth_date)],
            BIRTH_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_birth_year)],
            SEARCH_ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_artist)],
            SEARCH_TRACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_track)],
            GUESS_ANSWER: [CallbackQueryHandler(callback_handler)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("fact", cmd_fact))
    app.add_handler(CommandHandler("favorites", cmd_favorites_cmd))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))

    logger.info("Music90s Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
