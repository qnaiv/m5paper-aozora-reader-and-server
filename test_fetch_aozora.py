#!/usr/bin/env python3
"""
fetch_aozora.py のテストコード

主要な機能のテスト：
1. CSV解析機能のテスト
2. 文字数フィルタリング機能のテスト
3. テキストクリーニング機能のテスト
4. JSON出力機能のテスト
"""

import unittest
import tempfile
import json
import os
import sys
from unittest.mock import patch, MagicMock

# テスト対象モジュールをインポート
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
import fetch_aozora

class TestFetchAozora(unittest.TestCase):
    
    def test_parse_csv_data_with_filtering(self):
        """CSV解析と文字数フィルタリングのテスト"""
        # テスト用CSVデータ（文字数フィルタリングを検証）
        test_csv = """作品名,著者,文字数,url
        "短編作品",夏目漱石,300,http://example.com/short
        "中編作品",芥川龍之介,800,http://example.com/medium  
        "長編作品",森鴎外,1500,http://example.com/long
        "超短編",太宰治,50,http://example.com/very-short"""
        
        books = fetch_aozora.parse_csv_data(test_csv)
        
        # 500文字以上の作品のみがフィルタリングされていることを確認
        self.assertEqual(len(books), 2)  # 800文字と1500文字の作品のみ
        
        char_counts = [book['char_count'] for book in books]
        self.assertIn(800, char_counts)
        self.assertIn(1500, char_counts)
        self.assertNotIn(300, char_counts)  # 500文字未満はフィルタされる
        self.assertNotIn(50, char_counts)   # 500文字未満はフィルタされる
        
        # 作品情報の正確性確認
        medium_book = next(book for book in books if book['char_count'] == 800)
        self.assertEqual(medium_book['title'], '中編作品')
        self.assertEqual(medium_book['author'], '芥川龍之介')
        self.assertEqual(medium_book['url'], 'http://example.com/medium')

    def test_clean_aozora_text(self):
        """青空文庫テキストクリーニング機能のテスト"""
        # ルビ、注記、HTMLタグを含むテストテキスト
        test_text = """
        -------------------------------------------------------
        【テキスト中に現れる記号について】
        ※この作品は青空文庫で作られました。
        
        これは｜漢字《かんじ》のテストです。
        ［＃改丁］
        <ruby>漢字<rt>かんじ</rt></ruby>も含まれています。
        ※注意書きです。
        
        本文がここから始まります。
        ｜夏目《なつめ》漱石の作品です。
        ［＃ここで改行］
        <p>段落タグも除去されます。</p>
        
        -------------------------------------------------------
        底本：「夏目漱石全集」
        入力：青空文庫
        """
        
        cleaned = fetch_aozora.clean_aozora_text(test_text)
        
        # ルビが除去されていることを確認
        self.assertNotIn('｜', cleaned)
        self.assertNotIn('《', cleaned)
        self.assertNotIn('》', cleaned)
        
        # 注記が除去されていることを確認
        self.assertNotIn('［＃', cleaned)
        self.assertNotIn('］', cleaned)
        
        # HTMLタグが除去されていることを確認
        self.assertNotIn('<ruby>', cleaned)
        self.assertNotIn('<rt>', cleaned)
        self.assertNotIn('<p>', cleaned)
        self.assertNotIn('</p>', cleaned)
        
        # 前書き・後書きが除去されていることを確認
        self.assertNotIn('【テキスト中に現れる記号について】', cleaned)
        self.assertNotIn('底本：', cleaned)
        self.assertNotIn('入力：青空文庫', cleaned)
        
        # 本文は残っていることを確認
        self.assertIn('本文がここから始まります', cleaned)
        self.assertIn('夏目漱石の作品です', cleaned)  # ルビは除去されているが本文は残る

    def test_select_random_book(self):
        """ランダム作品選択のテスト"""
        test_books = [
            {'title': '作品1', 'author': '著者1', 'char_count': 600, 'url': 'http://example.com/1'},
            {'title': '作品2', 'author': '著者2', 'char_count': 700, 'url': 'http://example.com/2'},
            {'title': '作品3', 'author': '著者3', 'char_count': 800, 'url': 'http://example.com/3'}
        ]
        
        selected = fetch_aozora.select_random_book(test_books)
        
        # 選択された作品がリストに含まれていることを確認
        self.assertIn(selected, test_books)
        
        # 必要なフィールドが含まれていることを確認
        self.assertIn('title', selected)
        self.assertIn('author', selected)
        self.assertIn('char_count', selected)
        self.assertIn('url', selected)

    def test_save_json_output(self):
        """JSON出力機能のテスト"""
        # 一時ファイルを作成してテスト
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # テストデータ
            test_title = "テスト作品"
            test_author = "テスト著者"
            test_text = "これはテスト用の本文です。\n改行も含まれています。"
            
            # JSON保存実行
            fetch_aozora.save_json_output(test_title, test_author, test_text, temp_path)
            
            # 保存されたJSONファイルを読み込んで検証
            with open(temp_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            self.assertEqual(saved_data['title'], test_title)
            self.assertEqual(saved_data['author'], test_author)
            self.assertEqual(saved_data['text'], test_text)
            
        finally:
            # 一時ファイルを削除
            if os.path.exists(temp_path):
                os.unlink(temp_path)

class TestCharacterFiltering(unittest.TestCase):
    """文字数フィルタリング専用テストクラス"""
    
    def test_filtering_at_csv_parse_stage(self):
        """CSVパース段階で文字数フィルタリングが実行されることを確認"""
        test_csv = """作品名,著者,文字数,リンク
        "作品A",作者A,100,http://example.com/a
        "作品B",作者B,200,http://example.com/b
        "作品C",作者C,600,http://example.com/c
        "作品D",作者D,1000,http://example.com/d"""
        
        # parse_csv_data関数は内部で文字数500以上のフィルタリングを実行
        books = fetch_aozora.parse_csv_data(test_csv)
        
        # 500文字以上の作品のみが返されることを確認
        self.assertEqual(len(books), 2)
        
        char_counts = [book['char_count'] for book in books]
        self.assertEqual(set(char_counts), {600, 1000})
        
        # 500文字未満の作品は除外されている
        self.assertNotIn(100, char_counts)
        self.assertNotIn(200, char_counts)
    
    def test_min_characters_constant(self):
        """MIN_CHARACTERS定数の値を確認"""
        self.assertEqual(fetch_aozora.MIN_CHARACTERS, 500)

def run_functionality_demo():
    """実際の機能デモンストレーション"""
    print("=== 青空文庫スクレイピング機能デモ ===\n")
    
    # 1. 文字数フィルタリングのデモ
    print("1. 文字数フィルタリングのデモ:")
    demo_csv = """作品名,著者,文字数,リンク
    "短編A",夏目漱石,300,http://example.com/a
    "中編B",芥川龍之介,800,http://example.com/b  
    "長編C",森鴎外,1500,http://example.com/c
    "短編D",太宰治,150,http://example.com/d"""
    
    print("CSVデータ:")
    print(demo_csv)
    
    books = fetch_aozora.parse_csv_data(demo_csv)
    print(f"\n500文字以上でフィルタリング後: {len(books)}作品")
    for book in books:
        print(f"  - 「{book['title']}」by {book['author']} ({book['char_count']}文字)")
    
    # 2. テキストクリーニングのデモ
    print("\n2. テキストクリーニングのデモ:")
    demo_text = """
    【前書き】
    この作品について
    -------------------------------------------------------
    
    これは｜青空《あおぞら》文庫の作品です。
    ［＃改丁］
    <p>HTMLタグも含まれています。</p>
    ※注意書きです。
    
    本文の内容がここにあります。
    ｜夏目《なつめ》漱石の作品。
    
    -------------------------------------------------------
    底本：「全集」
    """
    
    print("クリーニング前:")
    print(repr(demo_text[:100] + "..."))
    
    cleaned = fetch_aozora.clean_aozora_text(demo_text)
    print("\nクリーニング後:")
    print(repr(cleaned))
    
    # 3. JSON出力のデモ  
    print("\n3. JSON出力形式のデモ:")
    demo_output = {
        'title': '夢十夜',
        'author': '夏目漱石', 
        'text': '第一夜\n\nこんな夢を見た。\n腕組をして枕元に座っていると、仰向に寝た女が、静かな声で「もう死にます」と云った。'
    }
    print(json.dumps(demo_output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    print("青空文庫スクレイピングスクリプトのテストを開始します...\n")
    
    # 機能デモンストレーション
    run_functionality_demo()
    
    print("\n" + "="*60)
    print("ユニットテスト実行:")
    print("="*60)
    
    # ユニットテスト実行
    unittest.main(argv=[''], verbosity=2, exit=False)
    
    print("\nテスト完了！")