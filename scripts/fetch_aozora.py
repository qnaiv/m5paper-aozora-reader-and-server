#!/usr/bin/env python3
"""
青空文庫スクレイピングスクリプト

青空文庫から毎日1作品をランダムに選んで、M5Paper用のJSON形式で出力する。
"""

import sys
import csv
import json
import random
import requests
import time
import zipfile
import io
import re
import os
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import chardet


class AozoraScraper:
    """青空文庫スクレイピングクラス"""
    
    # Google Sheets CSV export URL
    CSV_URL = "https://docs.google.com/spreadsheets/d/1n04e6POI04TBt-3HJUH10-T5cxhPZHcBWmFA4tSHjqE/export?format=csv&gid=288090143"
    
    # 最小文字数（これより短い作品はスキップ）
    MIN_CHARACTERS = 500
    
    # HTTPリクエストの設定
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    REQUEST_TIMEOUT = 30
    RETRY_DELAY = 2
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def fetch_book_list(self) -> List[Dict[str, Any]]:
        """Google SheetsからCSVを取得して作品リストを返す"""
        try:
            print("青空文庫作品リストを取得中...")
            response = self.session.get(self.CSV_URL, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # CSVをパース
            csv_text = response.content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_text))
            
            books = []
            for row in csv_reader:
                # 必要なフィールドが存在し、文字数が条件を満たすかチェック
                if self._is_valid_book_row(row):
                    books.append({
                        'title': row.get('作品名', '').strip(),
                        'author': row.get('姓', '').strip() + row.get('名', '').strip(),
                        'text_url': row.get('テキストファイルURL', '').strip(),
                        'characters': self._get_character_count(row)
                    })
            
            print(f"取得した作品数: {len(books)}件")
            return books
            
        except Exception as e:
            print(f"エラー: 作品リスト取得に失敗しました: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _is_valid_book_row(self, row: Dict[str, str]) -> bool:
        """CSVの行が有効な作品データかチェック"""
        required_fields = ['作品名', 'テキストファイルURL']
        
        # 必須フィールドの存在確認
        for field in required_fields:
            if not row.get(field, '').strip():
                return False
        
        # 文字数チェック（CSVに文字数情報がある場合のみ）
        try:
            char_count = self._get_character_count(row)
            # 文字数情報がある場合のみフィルタリング（0の場合は後で実テキストで判定）
            if char_count > 0 and char_count < self.MIN_CHARACTERS:
                return False
        except (ValueError, TypeError):
            # 文字数チェックでエラーが発生しても継続（後で実テキストで判定）
            pass
        
        return True
    
    def _get_character_count(self, row: Dict[str, str]) -> int:
        """CSVから文字数を取得する"""
        # 可能性のあるフィールド名を順番に試す
        possible_fields = ['文字数', '文字遣い種別', 'character_count', 'length']
        
        for field in possible_fields:
            value = row.get(field, '').strip()
            if value:
                try:
                    # 数値として変換可能かチェック
                    return int(float(value))
                except (ValueError, TypeError):
                    continue
        
        # 文字数情報が見つからない場合は0を返す（後でテキスト長で判定）
        return 0
    
    def select_random_book(self, books: List[Dict[str, Any]]) -> Dict[str, Any]:
        """リストからランダムに1作品を選択"""
        if not books:
            print("エラー: 選択可能な作品がありません", file=sys.stderr)
            sys.exit(1)
        
        selected = random.choice(books)
        print(f"選択された作品: 『{selected['title']}』 著者: {selected['author']}")
        return selected
    
    def download_text(self, book: Dict[str, Any]) -> str:
        """作品のテキストファイルをダウンロードして内容を返す"""
        url = book['text_url']
        if not url:
            print("エラー: テキストファイルのURLが不正です", file=sys.stderr)
            sys.exit(1)
        
        try:
            print(f"テキストファイルをダウンロード中: {url}")
            response = self.session.get(url, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # ファイルタイプを判定してテキストを抽出
            if url.lower().endswith('.zip'):
                return self._extract_text_from_zip(response.content)
            else:
                return self._decode_text_content(response.content)
                
        except Exception as e:
            print(f"エラー: テキストダウンロードに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _extract_text_from_zip(self, zip_content: bytes) -> str:
        """ZIPファイルからテキストを抽出"""
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
                # ZIP内のテキストファイルを探す
                txt_files = [name for name in zip_file.namelist() if name.lower().endswith('.txt')]
                
                if not txt_files:
                    raise ValueError("ZIP内にテキストファイルが見つかりません")
                
                # 最初のテキストファイルを使用
                with zip_file.open(txt_files[0]) as txt_file:
                    content = txt_file.read()
                    return self._decode_text_content(content)
                    
        except Exception as e:
            raise Exception(f"ZIP展開エラー: {e}")
    
    def _decode_text_content(self, content: bytes) -> str:
        """バイトデータからテキストをデコード（Shift_JIS -> UTF-8）"""
        try:
            # まずShift_JISでデコードを試す（青空文庫の標準）
            return content.decode('shift_jis', errors='replace')
        except UnicodeDecodeError:
            try:
                # 文字エンコードを検出
                detected = chardet.detect(content)
                encoding = detected.get('encoding', 'utf-8')
                return content.decode(encoding, errors='replace')
            except Exception:
                # 最終手段としてUTF-8
                return content.decode('utf-8', errors='replace')
    
    def clean_text(self, raw_text: str) -> str:
        """青空文庫のテキストをクリーニング"""
        text = raw_text
        
        # 1. ルビを除去（｜漢字《かんじ》→漢字）
        text = re.sub(r'｜([^《]+)《[^》]*》', r'\\1', text)
        text = re.sub(r'([^｜])《[^》]*》', r'\\1', text)
        
        # 2. 注記を除去（［＃...］）
        text = re.sub(r'［＃[^］]*］', '', text)
        
        # 3. HTMLタグを除去（念のため）
        soup = BeautifulSoup(text, 'html.parser')
        text = soup.get_text()
        
        # 4. 前書き・後書き・著作権表示を除去（本文抽出）
        text = self._extract_main_content(text)
        
        # 5. 余分な改行・空白を整理
        text = re.sub(r'\\n{3,}', '\\n\\n', text)  # 3つ以上の連続改行を2つに
        text = re.sub(r'[ \\t]+', ' ', text)  # 連続スペース・タブを1つのスペースに
        text = text.strip()
        
        return text
    
    def _extract_main_content(self, text: str) -> str:
        """テキストから本文部分のみを抽出"""
        lines = text.split('\\n')
        
        # 本文開始・終了の目印を探す
        start_idx = 0
        end_idx = len(lines)
        
        # 一般的な前書きの終了パターン
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if (line_stripped.startswith('-------') or
                '本文' in line_stripped or
                re.search(r'第[一二三四五六七八九十壱弐参肆伍陸漆捌玖拾百千万０-９]+[章回話編部巻]', line_stripped)):
                start_idx = i
                break
        
        # 一般的な後書きの開始パターン（後ろから検索）
        for i in range(len(lines) - 1, -1, -1):
            line_stripped = lines[i].strip()
            if (line_stripped.startswith('-------') or
                '底本：' in line_stripped or
                '入力：' in line_stripped or
                '校正：' in line_stripped or
                '青空文庫' in line_stripped or
                'http://www.aozora.gr.jp/' in line_stripped):
                end_idx = i
                break
        
        # 抽出した本文を結合
        main_content = '\\n'.join(lines[start_idx:end_idx])
        
        # 短すぎる場合は元のテキストを返す
        if len(main_content.strip()) < self.MIN_CHARACTERS:
            return text
        
        return main_content
    
    def save_json(self, book_data: Dict[str, Any], output_path: str):
        """JSON形式で保存"""
        try:
            # 出力ディレクトリを作成
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(book_data, f, ensure_ascii=False, indent=2)
            
            print(f"JSON保存完了: {output_path}")
            print(f"タイトル: {book_data['title']}")
            print(f"著者: {book_data['author']}")
            print(f"文字数: {len(book_data['text'])}文字")
            
        except Exception as e:
            print(f"エラー: JSON保存に失敗しました: {e}", file=sys.stderr)
            sys.exit(1)


def main():
    """メイン処理"""
    print("青空文庫スクレイピング開始...")
    
    # 出力パス
    output_path = "data/todays_book.json"
    
    try:
        scraper = AozoraScraper()
        
        # 1. 作品リストを取得
        books = scraper.fetch_book_list()
        
        # 2. ランダムに1作品を選択
        selected_book = scraper.select_random_book(books)
        
        # 3. テキストをダウンロード
        raw_text = scraper.download_text(selected_book)
        
        # リクエスト間隔を開ける
        time.sleep(scraper.RETRY_DELAY)
        
        # 4. テキストをクリーニング
        cleaned_text = scraper.clean_text(raw_text)
        
        # 5. 最終的な文字数チェック
        if len(cleaned_text) < scraper.MIN_CHARACTERS:
            print(f"警告: クリーニング後のテキストが短すぎます({len(cleaned_text)}文字)")
            print("再試行はせず、このまま出力します")
        
        # 6. JSON形式で保存
        result = {
            "title": selected_book['title'],
            "author": selected_book['author'],
            "text": cleaned_text
        }
        
        scraper.save_json(result, output_path)
        
        print("\\n青空文庫スクレイピング完了！")
        
    except KeyboardInterrupt:
        print("\\n処理が中断されました", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"予期しないエラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()