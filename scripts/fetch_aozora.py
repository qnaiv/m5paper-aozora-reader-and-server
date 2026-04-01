#!/usr/bin/env python3
"""
青空文庫から毎日1作品をランダムに選んでテキストを取得し、
M5Paperで表示可能なJSON形式で出力するPythonスクリプト

要件:
- Google Sheetsから作品リストCSVを取得
- 文字数500文字以上の作品のみを対象としてフィルタリング
- ランダムに1作品を選択
- テキストファイル（ZIP/TXT）をダウンロード
- 文字エンコード変換（Shift_JIS → UTF-8）
- 青空文庫記法のクリーニング（ルビ、注記、HTMLタグ除去）
- data/todays_book.json として出力
"""

import requests
import json
import random
import re
import sys
import os
import zipfile
import tempfile
import io
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import chardet

# Google Sheetsの青空文庫作品リストURL（CSV形式）
AOZORA_CSV_URL = "https://docs.google.com/spreadsheets/d/1n04e6POI04TBt-3HJUH10-T5cxhPZHcBWmFA4tSHjqE/export?format=csv&gid=288090143"

# 文字数の下限
MIN_CHARACTERS = 500

# ユーザーエージェント設定
USER_AGENT = "M5Paper Aozora Reader Bot/1.0 (+https://github.com/qnaiv/m5paper-aozora-reader-and-server)"

# リクエスト間隔（秒）
REQUEST_INTERVAL = 1

def get_csv_data():
    """Google SheetsからCSVデータを取得"""
    print("青空文庫作品リストを取得中...")
    
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(AOZORA_CSV_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        # CSVデータをテキストとして取得
        csv_text = response.text
        return csv_text
    except requests.RequestException as e:
        print(f"エラー: CSVデータの取得に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

def parse_csv_data(csv_text):
    """CSVデータを解析して作品リストを取得"""
    print("作品リストを解析中...")
    
    lines = csv_text.strip().split('\n')
    if len(lines) < 2:
        print("エラー: CSVデータが不正です", file=sys.stderr)
        sys.exit(1)
    
    # ヘッダー行を取得
    header = lines[0].split(',')
    
    # 文字数カラムを探す（複数のパターンに対応）
    char_count_col = None
    possible_char_cols = ['文字数', 'characters', '文字数計', 'char_count']
    
    for i, col_name in enumerate(header):
        for possible_name in possible_char_cols:
            if possible_name in col_name:
                char_count_col = i
                break
        if char_count_col is not None:
            break
    
    if char_count_col is None:
        print(f"エラー: 文字数カラムが見つかりません。ヘッダー: {header}", file=sys.stderr)
        sys.exit(1)
    
    print(f"文字数カラムを検出: {header[char_count_col]} (位置: {char_count_col})")
    
    # 必要なカラムを探す
    title_col = None
    author_col = None
    url_col = None
    
    for i, col_name in enumerate(header):
        if '作品名' in col_name or 'title' in col_name.lower():
            title_col = i
        elif '著者' in col_name or 'author' in col_name.lower():
            author_col = i
        elif 'url' in col_name.lower() or 'リンク' in col_name:
            url_col = i
    
    if title_col is None or author_col is None or url_col is None:
        print(f"エラー: 必要なカラムが見つかりません。ヘッダー: {header}", file=sys.stderr)
        sys.exit(1)
    
    print(f"検出したカラム - タイトル: {header[title_col]}, 著者: {header[author_col]}, URL: {header[url_col]}")
    
    # データ行を解析
    books = []
    for line_num, line in enumerate(lines[1:], 2):
        try:
            cols = line.split(',')
            if len(cols) <= max(char_count_col, title_col, author_col, url_col):
                continue
            
            # 文字数を取得・検証
            char_count_str = cols[char_count_col].strip()
            if not char_count_str or char_count_str == '':
                continue
                
            try:
                char_count = int(char_count_str)
            except ValueError:
                # 数値でない場合はスキップ
                continue
            
            # 文字数フィルタリング（ここで事前フィルタリング実施）
            if char_count < MIN_CHARACTERS:
                continue
            
            title = cols[title_col].strip().strip('"')
            author = cols[author_col].strip().strip('"') 
            url = cols[url_col].strip().strip('"')
            
            if title and author and url:
                books.append({
                    'title': title,
                    'author': author,
                    'url': url,
                    'char_count': char_count
                })
                
        except (IndexError, ValueError) as e:
            # 行の解析エラーはスキップ
            continue
    
    print(f"文字数{MIN_CHARACTERS}文字以上の作品を{len(books)}件発見")
    
    if len(books) == 0:
        print("エラー: 条件を満たす作品が見つかりませんでした", file=sys.stderr)
        sys.exit(1)
    
    return books

def select_random_book(books):
    """作品リストからランダムに1作品を選択"""
    selected = random.choice(books)
    print(f"選択された作品: 「{selected['title']}」by {selected['author']} ({selected['char_count']}文字)")
    return selected

def download_text(book_url):
    """作品のテキストファイルをダウンロード"""
    print(f"作品ページにアクセス中: {book_url}")
    
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(book_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        time.sleep(REQUEST_INTERVAL)  # サーバー負荷軽減
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # テキストファイルのリンクを探す
        text_links = []
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href and ('.txt' in href or '.zip' in href):
                # 相対URLを絶対URLに変換
                full_url = urljoin(book_url, href)
                text_links.append(full_url)
        
        if not text_links:
            print("エラー: テキストファイルのリンクが見つかりませんでした", file=sys.stderr)
            return None
        
        # 最初に見つかったテキストファイルをダウンロード
        text_url = text_links[0]
        print(f"テキストファイルをダウンロード中: {text_url}")
        
        time.sleep(REQUEST_INTERVAL)  # サーバー負荷軽減
        
        response = requests.get(text_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        return response.content, text_url.endswith('.zip')
        
    except requests.RequestException as e:
        print(f"エラー: テキストダウンロードに失敗しました: {e}", file=sys.stderr)
        return None

def extract_text_content(content, is_zip):
    """テキストファイルからコンテンツを抽出"""
    if is_zip:
        print("ZIPファイルを展開中...")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
                # 最初のテキストファイルを探す
                for file_name in zip_file.namelist():
                    if file_name.endswith('.txt'):
                        with zip_file.open(file_name) as txt_file:
                            raw_content = txt_file.read()
                        break
                else:
                    print("エラー: ZIP内にテキストファイルが見つかりませんでした", file=sys.stderr)
                    return None
        except zipfile.BadZipFile:
            print("エラー: ZIPファイルが破損しています", file=sys.stderr)
            return None
    else:
        raw_content = content
    
    # 文字エンコードを検出・変換
    encoding = chardet.detect(raw_content)['encoding']
    print(f"検出されたエンコーディング: {encoding}")
    
    try:
        if encoding and encoding.lower().startswith('shift'):
            # Shift_JISとして読み込み
            text = raw_content.decode('shift_jis', errors='replace')
        else:
            # その他のエンコーディング
            text = raw_content.decode(encoding or 'utf-8', errors='replace')
    except (UnicodeDecodeError, LookupError):
        # フォールバック: UTF-8で試す
        try:
            text = raw_content.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            print("エラー: テキストのデコードに失敗しました", file=sys.stderr)
            return None
    
    return text

def clean_aozora_text(text):
    """青空文庫記法のクリーニング"""
    print("テキストクリーニング中...")
    
    # 前書き・後書きの除去パターン
    # 作品の本文開始を示すマーカーを探す
    text_markers = [
        r'-------------------------------------------------------',
        r'【テキスト中に現れる記号について】',
        r'底本：',
        r'入力：',
        r'校正：',
        r'※',
        r'［＃',
    ]
    
    # 本文開始位置を探す
    main_start = 0
    for marker in text_markers:
        match = re.search(marker, text)
        if match:
            # マーカー以降を本文とする
            main_start = max(main_start, match.end())
    
    # 本文終了位置を探す（底本情報の開始）
    end_markers = [
        r'底本：',
        r'※［＃',
        r'（青空文庫',
        r'-------------------------------------------------------',
    ]
    
    main_end = len(text)
    for marker in end_markers:
        # 後半部分で検索
        search_start = len(text) // 2
        match = re.search(marker, text[search_start:])
        if match:
            main_end = min(main_end, search_start + match.start())
    
    # 本文部分を抽出
    if main_start > 0 or main_end < len(text):
        text = text[main_start:main_end]
        print(f"前書き・後書きを除去（{main_start}〜{main_end}文字目）")
    
    # 青空文庫記法のクリーニング
    
    # 1. ルビの除去（｜漢字《かんじ》）
    text = re.sub(r'｜[^《]*《[^》]*》', '', text)
    text = re.sub(r'《[^》]*》', '', text)
    
    # 2. 注記の除去（［＃...］）
    text = re.sub(r'［＃[^］]*］', '', text)
    
    # 3. HTMLタグの除去
    text = re.sub(r'<[^>]+>', '', text)
    
    # 4. その他の記号の除去
    text = re.sub(r'※', '', text)
    
    # 5. 余分な改行・空白の整理
    text = re.sub(r'\n{3,}', '\n\n', text)  # 3つ以上の改行を2つに
    text = re.sub(r'[ \t]+', ' ', text)     # 複数のスペース・タブを1つに
    text = text.strip()
    
    print(f"クリーニング後の文字数: {len(text)}文字")
    
    # 短すぎる場合は警告
    if len(text) < 100:
        print("警告: クリーニング後のテキストが短すぎます", file=sys.stderr)
    
    return text

def save_json_output(title, author, text, output_path):
    """JSON形式で出力を保存"""
    print(f"JSON出力を保存中: {output_path}")
    
    output_data = {
        'title': title,
        'author': author, 
        'text': text
    }
    
    # 出力ディレクトリを作成
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"正常に保存されました: {output_path}")
        print(f"  タイトル: {title}")
        print(f"  著者: {author}")
        print(f"  文字数: {len(text)}文字")
        
    except IOError as e:
        print(f"エラー: ファイル保存に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    """メイン処理"""
    print("青空文庫スクレイピングスクリプトを開始します...")
    
    # 1. CSVデータ取得
    csv_data = get_csv_data()
    
    # 2. 作品リスト解析・フィルタリング
    books = parse_csv_data(csv_data)
    
    # 3. ランダム選択
    selected_book = select_random_book(books)
    
    # 4. テキストダウンロード
    result = download_text(selected_book['url'])
    if result is None:
        sys.exit(1)
    
    content, is_zip = result
    
    # 5. テキスト抽出
    text = extract_text_content(content, is_zip)
    if text is None:
        sys.exit(1)
    
    # 6. テキストクリーニング
    cleaned_text = clean_aozora_text(text)
    
    # 7. JSON出力
    output_path = 'data/todays_book.json'
    save_json_output(selected_book['title'], selected_book['author'], cleaned_text, output_path)
    
    print("処理が正常に完了しました!")

if __name__ == "__main__":
    main()