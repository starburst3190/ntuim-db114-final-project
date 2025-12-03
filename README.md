# 114-1 資料庫管理 - TCG ONLINE SHOP

## 專案簡介
隨著卡牌遊戲在全球的流行，卡牌店已不僅僅是販售場所，更是玩家交流、比賽與收藏的重要場域。
然而，實體店面往往缺乏一套整合式系統，能同時管理卡牌庫存、會員資料、比賽報名與玩家活動記錄。
與此同時，玩家也在苦於清點欲組牌組缺少的卡牌，而且玩家之間的情感連結是極少的，沒有系統協助列出活動排程，經常會錯過活動，或是朋友沒到。

這些問題就讓「TCG ONLINE SHOP」來解決吧！
在「TCG ONLINE SHOP」，我們提供兩種用戶，一種是一般使用者，名為 Player，而另一種是業務經營者，名為 Shop。
Player 端著重於收藏與互動，而 Shop 端則是商業營運、推廣兼具。

## 使用步驟
1. 安裝套件
```bash
pip install -r requirements.txt
```
2. 啟用後端
```bash

```
3. 啟用前端
```bash

```

## 技術細節

## 專案架構
```
ntuim-db114-final-project/
├── backend/
│   ├── main.py      # FastAPI
│   └── db.py        # 連線至資料庫
├── frontend/
│   └── app.py       # Streamlit
├── .env             # 儲存環境變數 (要自己創建)
├── .env.example     # .env 檔的範例
├── requirements.txt # 套件清單
└── README.md
```

## 開發環境
- Windows 11
    - Python 3.12.10
        - 套件版本由 `requirements.txt` 管理
    - PostgreSQL 17.6
    - MongoDB Atlas (**預計，沒有用到的話改掉**)