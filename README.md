# 🥚 REC-G｜RSS Egg Collection Garden

**Rec-Garden ── 庭の西にある、卵を集める一角。**
*The west wing of your Farmers' Digital Garden.*

ブログ、note、Bluesky、ポッドキャスト。あちこちで産んだ卵（記事や作品）を、ひとつの庭に集める仕組みです。
呼び名は **集卵処**（しゅうらんどこ）。

- 記事は引っ越さない。それぞれの場所に置いたまま、**表紙と目次だけ**をここに並べる
- 人が書くのは **テキスト二枚** だけ。あとは仕入れ係（GitHub Actions）が一日二回、卵を集める
- 新着順・棚ごと・ぜんぶ（題名順）の三つの引き方で眺められる
- 集めた新着は、まとめて一本の RSS（`feed.xml`）にもなる

見本：[CHIC TEC の集卵処](https://ittekiou.github.io/CHIC-TEC/rec-g/)

---

## はじめかた

1. 右上の **Use this template** →「Create a new repository」で、自分のアカウントに写す（Public にする）
2. 写した箱の **Settings → Pages** で、Branch を `main`・`/ (root)` にして Save
3. `eggs.txt` を開き、鉛筆マークで編集して、自分のページの URL を書いて **Commit changes**
4. **Actions** タブで「Collect eggs」が動き終わったら、`https://あなたの名前.github.io/REC-G/` に庭ができている

仕入れ係がうまく動かないとき（保存のところで 403 のエラー）は、Settings → Actions → General のいちばん下、Workflow permissions を「Read and write」にする。

## テキスト二枚

| ファイル | 書くこと |
|---|---|
| `eggs.txt` | 卵の一覧。ふだん見ているページの URL を一行に一つ。`URL ｜ 表示名` で名前も付けられる |
| `shelves.txt` | 棚割り。はじめはさわらなくてよい。棚を分けたくなったら見出しを足す |

`shelves.txt` の決まりごと：

- `## 棚id 名前` が棚の見出し。見出しの順が棚の順、その下の URL の順が棚の中の順
- `## * 名前` の棚には、どの棚にも書いていない卵が入る
- 棚id `info` の卵は、どの見せ方でも罫線の下に分けて並ぶ（便りなどに）

## 集められる場所

note（アカウント・マガジン）、Bluesky、Medium、Substack は URL から直接。
はてなブログ、YouTube、WordPress など、ページに RSS の印があるところはページから探す。
X と Instagram は RSS を出していないので、集められない。

## 庭の中の位置

REC-G は庭そのものではなく、庭の一角です。

- **Farmers' Digital Gardens（FDGs）**：庭そのもの。各自の場所
- **REC-G**：その西で、卵を集める集卵処
- **[DyXis](https://ittekiou.github.io/dyxis/)**：庭と庭をつなぐ地下茎。つなぎたくなったら、自分の巣に立札（`nest.json`）を一枚立てる
- **[CHIC TEC](https://ittekiou.github.io/CHIC-TEC/)**：まだ自分の箱を持たない人に、集卵処付きの私書箱を半年貸す巣立ち支援

GitHub の箱を持つ前に試したい人は、CHIC TEC で借りてから、慣れたらここを写して巣立つ、という順番もあります。

## 巣立ち・引っ越し

庭の本体はテキスト二枚です。どこへ引っ越すときも、二枚を持って出ればいい。

---

2026年11月、一狄翁と Echodemy の AI たち（綴音・響詠・謡理）が置きはじめた。だれのものでもない。
文章は CC BY-SA 4.0、コードは MIT License。
