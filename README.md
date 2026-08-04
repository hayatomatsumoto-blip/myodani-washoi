# 名谷ワッショイ（公式サイト）

GitHub Pages で公開する静的サイトです。

## 名谷の最新情報

- 第1版の更新経路は **自動収集のみ**（SNSには依存しない）
- 情報源：須磨パティオ（WordPress REST）／おでかけKOBE（sitemap + SSR）
- 実行：GitHub Actions（毎日）または `python3 scripts/collect_news.py`

## ローカル

```bash
python3 scripts/collect_news.py
python3 -m http.server 8080
# http://127.0.0.1:8080/
```

## メンバー投稿

8/25以降に追加予定。承認なし（投入＝掲載）。
