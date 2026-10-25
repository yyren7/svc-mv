#!/bin/bash
# 用模板开一首新歌：建 cases/<名字>/，放好 song.json、credits.txt 的草稿。本地、服务器上都能跑（只写文本文件）。
#   bash templates/kue_stars/new_song.sh <名字> ["歌名"] ["原唱"] ["翻唱"]
# 然后：改 song.json、credits.txt，提交、推送；服务器上 git pull，把混音、人声分轨、歌词放进 cases/<名字>/audio/
# （不进仓库），跑 preview.sh。
set -euo pipefail
NAME=${1:?"用法：new_song.sh <名字> [歌名] [原唱] [翻唱]"}
TITLE=${2:-$NAME}
ARTIST=${3:-}
COVER=${4:-}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
C=$ROOT/cases/$NAME
[ -e "$C/song.json" ] && { echo "$C/song.json 已经有了"; exit 1; }
mkdir -p "$C/audio"
SUB="$ARTIST${COVER:+ · cover $COVER}"
cat > "$C/song.json" <<JSON
{
  "title": "$TITLE",
  "artist": "$ARTIST",
  "sub": "$SUB",
  "mix": "audio/mix.wav",
  "vocal": "audio/vocal.flac",
  "lyrics": "audio/lyrics.lrc",
  "lyrics_cn": "audio/lyrics_cn.lrc",
  "lyrics_offset": 0.15,
  "credits": "credits.txt"
}
JSON
cat > "$C/credits.txt" <<TXT
$TITLE
原曲　$ARTIST
翻唱　$COVER
插画　AI 绘制
TXT
cat > "$C/README.md" <<MD
# $TITLE · 一图流 PV

用 [templates/kue_stars](../../templates/kue_stars/README.md) 做的：kue 的星空花田插画，换了歌和文字。

- 歌名、文件：\`song.json\`；制作信息：\`credits.txt\`；段落、镜头、流星、标题时机：\`plan.json\`（\`plan.py make\` 排的草稿，可以手改）
- 音频、歌词放在 \`audio/\`（不进仓库）
MD
echo "-> $C：改好 song.json、credits.txt，音频和歌词放进 $C/audio/"
