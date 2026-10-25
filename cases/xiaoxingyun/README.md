# 小幸运 · 一图流 PV

用 [templates/kue_stars](../../templates/kue_stars/README.md) 做的：kue 的星空花田插画，换了歌和文字。

- 歌名、文件：`song.json`；制作信息：`credits.txt`；段落、镜头、流星、标题时机：`plan.json`（`plan.py make` 排的草稿，可以手改）
- 音频、歌词放在 `audio/`（不进仓库）

## 音频和歌词

- 混音：`music/小幸运_旬夏_全转换.flac`（旬夏的 DDSP-SVC 全转换）。开头 3 秒混进了人说话，从 3.15 秒的第一个吉他音
  （前面正好一小段静音）剪开，剪口 5 毫秒淡入，前面留 1 秒空白 -> `audio/mix.wav`，263.6 秒。
- 人声分轨：`audio/vocal.flac`，用服务器上 DDSP-SVC 的 `bs_leap_xe_voc`（BS-Roformer）从剪好的混音里分出来。
- 歌词：网易云 id 3343236872 那条（时长 263.8 秒，和剪完的一样长）的 LRC。对齐办法：分出来的人声在两句之间几乎是
  完全静音，句子前有停顿的 10 句取静音后第一次超过 −60 dB 的那一帧，都比 LRC 晚 0.37 秒（±0.07）；连着唱、
  前面没有静音的句子和空行（间奏开始）统一推后 0.37 秒 -> `audio/lyrics.lrc`。字幕再提前 0.25 秒出（`lyrics_offset`），
  和 kimishira 成片里的手感一样。whisper 的字级时间在歌里系统性偏早，对不准。
- 剪好的混音、人声、歌词也备份在 AutoDL 的 `/root/autodl-tmp/backup/svc-mv/music/`。
