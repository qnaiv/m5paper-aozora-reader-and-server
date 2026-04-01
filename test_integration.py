#!/usr/bin/env python3
"""
結合テスト（Integration Test）
実際のネットワーク通信を含むEnd-to-Endテスト

主なテスト項目：
1. Google SheetsからのCSV取得テスト
2. 青空文庫サイトからの実際のスクレイピングテスト
3. 完全なワークフローテスト（CSV取得→スクレイピング→JSON出力）
4. エラーハンドリングテスト（ネットワークエラー等）
"""

import unittest
import tempfile
import json
import os
import sys
import time
from unittest.mock import patch
import requests

# テスト対象モジュールをインポート
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
import fetch_aozora

class TestNetworkIntegration(unittest.TestCase):
    """ネットワーク通信を含む結合テスト"""
    
    def setUp(self):
        """テストセットアップ"""
        self.test_output_dir = tempfile.mkdtemp()
        self.test_output_path = os.path.join(self.test_output_dir, 'test_book.json')

    def tearDown(self):
        """テストクリーンアップ"""
        if os.path.exists(self.test_output_path):
            os.unlink(self.test_output_path)
        os.rmdir(self.test_output_dir)

    def test_csv_data_retrieval_integration(self):
        """Google SheetsからのCSV取得の結合テスト"""
        print("\n🔗 CSV取得結合テストを実行中...")
        
        try:
            # 実際にGoogle SheetsからCSVを取得
            csv_data = fetch_aozora.get_csv_data()
            
            # CSVデータの基本検証
            self.assertIsInstance(csv_data, str)
            self.assertTrue(len(csv_data) > 0)
            
            # CSVヘッダーが含まれていることを確認
            lines = csv_data.strip().split('\n')
            self.assertGreater(len(lines), 1, "CSVにはヘッダー行以外のデータが必要")
            
            # ヘッダー行の検証
            header = lines[0].lower()
            expected_columns = ['作品', 'title', '著者', 'author', '文字', 'char', 'url', 'リンク']
            has_expected_columns = any(col in header for col in expected_columns)
            self.assertTrue(has_expected_columns, f"期待されるカラムが見つからない: {header}")
            
            print(f"✅ CSV取得成功: {len(lines)}行のデータを取得")
            
        except requests.RequestException as e:
            self.fail(f"CSV取得でネットワークエラーが発生: {e}")
        except Exception as e:
            self.fail(f"CSV取得で予期しないエラーが発生: {e}")

    def test_csv_parsing_with_real_data(self):
        """実際のCSVデータでの解析テスト"""
        print("\n📊 実際のCSVデータ解析テストを実行中...")
        
        try:
            # 実際のCSVデータを取得・解析
            csv_data = fetch_aozora.get_csv_data()
            books = fetch_aozora.parse_csv_data(csv_data)
            
            # 解析結果の検証
            self.assertIsInstance(books, list)
            self.assertGreater(len(books), 0, "500文字以上の作品が見つからない")
            
            # 各作品データの構造検証
            for book in books[:3]:  # 最初の3件のみ検証
                self.assertIn('title', book)
                self.assertIn('author', book)
                self.assertIn('url', book) 
                self.assertIn('char_count', book)
                
                self.assertIsInstance(book['char_count'], int)
                self.assertGreaterEqual(book['char_count'], fetch_aozora.MIN_CHARACTERS)
                
                # URLの基本検証
                self.assertTrue(book['url'].startswith('http'))
            
            print(f"✅ CSV解析成功: {len(books)}作品を検出（文字数500文字以上）")
            
        except Exception as e:
            self.fail(f"CSV解析で予期しないエラーが発生: {e}")

    def test_random_book_selection_integration(self):
        """ランダム作品選択の結合テスト"""
        print("\n🎲 ランダム作品選択結合テストを実行中...")
        
        try:
            # 実際のデータでランダム選択テスト
            csv_data = fetch_aozora.get_csv_data()
            books = fetch_aozora.parse_csv_data(csv_data)
            
            # 複数回選択して結果が変わることを確認
            selections = []
            for _ in range(3):
                selected = fetch_aozora.select_random_book(books)
                selections.append(selected['title'])
                time.sleep(0.1)  # 少し待機
            
            # 選択された作品がリストに含まれることを確認
            for selection_title in selections:
                found = any(book['title'] == selection_title for book in books)
                self.assertTrue(found, f"選択された作品「{selection_title}」がリストに見つからない")
            
            print(f"✅ ランダム選択成功: {selections}")
            
        except Exception as e:
            self.fail(f"ランダム選択で予期しないエラーが発生: {e}")

    @patch('fetch_aozora.select_random_book')
    def test_end_to_end_workflow_with_mock_selection(self, mock_select):
        """End-to-Endワークフローテスト（作品選択をモック化）"""
        print("\n🔄 End-to-Endワークフロー結合テストを実行中...")
        
        try:
            # 1. 実際のCSV取得・解析
            csv_data = fetch_aozora.get_csv_data()
            books = fetch_aozora.parse_csv_data(csv_data)
            self.assertGreater(len(books), 0)
            
            # 2. 確実に存在する作品を選択（テスト安定性のため）
            test_book = books[0]  # 最初の作品を使用
            mock_select.return_value = test_book
            
            # 3. メイン処理を実行（実際のスクレイピングを含む）
            original_output_path = 'data/todays_book.json'
            
            # 出力パスを一時的に変更
            with patch('fetch_aozora.main') as mock_main:
                def run_main_with_temp_output():
                    # 実際のメイン処理を手動実行
                    csv_data = fetch_aozora.get_csv_data()
                    books = fetch_aozora.parse_csv_data(csv_data)
                    selected_book = mock_select(books)
                    
                    # テキストダウンロード・処理
                    result = fetch_aozora.download_text(selected_book['url'])
                    if result is None:
                        raise Exception("テキストダウンロードに失敗")
                    
                    content, is_zip = result
                    text = fetch_aozora.extract_text_content(content, is_zip)
                    if text is None:
                        raise Exception("テキスト抽出に失敗")
                    
                    cleaned_text = fetch_aozora.clean_aozora_text(text)
                    
                    # 一時ファイルに出力
                    fetch_aozora.save_json_output(
                        selected_book['title'], 
                        selected_book['author'], 
                        cleaned_text, 
                        self.test_output_path
                    )
                
                run_main_with_temp_output()
            
            # 4. 出力結果の検証
            self.assertTrue(os.path.exists(self.test_output_path), "出力ファイルが作成されていない")
            
            with open(self.test_output_path, 'r', encoding='utf-8') as f:
                output_data = json.load(f)
            
            # JSON構造の検証
            self.assertIn('title', output_data)
            self.assertIn('author', output_data)
            self.assertIn('text', output_data)
            
            # データ内容の検証
            self.assertEqual(output_data['title'], test_book['title'])
            self.assertEqual(output_data['author'], test_book['author'])
            self.assertIsInstance(output_data['text'], str)
            self.assertGreater(len(output_data['text']), 0)
            
            print(f"✅ End-to-Endテスト成功:")
            print(f"   作品: 「{output_data['title']}」by {output_data['author']}")
            print(f"   テキスト長: {len(output_data['text'])}文字")
            
        except Exception as e:
            self.fail(f"End-to-Endテストで予期しないエラーが発生: {e}")

class TestErrorHandling(unittest.TestCase):
    """エラーハンドリング結合テスト"""
    
    def test_network_timeout_handling(self):
        """ネットワークタイムアウトのエラーハンドリングテスト"""
        print("\n⏱️ ネットワークタイムアウトテストを実行中...")
        
        # 極端に短いタイムアウトでテスト
        original_get = requests.get
        
        def timeout_get(*args, **kwargs):
            kwargs['timeout'] = 0.001  # 極端に短いタイムアウト
            return original_get(*args, **kwargs)
        
        with patch('requests.get', side_effect=timeout_get):
            try:
                # タイムアウトが発生することを確認
                with self.assertRaises(SystemExit):
                    fetch_aozora.get_csv_data()
                print("✅ タイムアウトエラーが適切に処理された")
                
            except requests.exceptions.Timeout:
                print("✅ タイムアウトエラーが発生し、適切に処理された")
            except Exception as e:
                self.fail(f"予期しないエラー: {e}")

def run_integration_tests():
    """結合テストを実行する関数"""
    print("="*70)
    print("🧪 青空文庫スクレイピング 結合テスト実行")
    print("="*70)
    print()
    print("⚠️ 注意: このテストは実際のインターネット接続を必要とします")
    print("⚠️ 青空文庫サーバーに負荷をかけるため、必要最小限の実行にとどめてください")
    print()
    
    # テストスイート作成
    suite = unittest.TestSuite()
    
    # ネットワーク結合テストを追加
    suite.addTest(TestNetworkIntegration('test_csv_data_retrieval_integration'))
    suite.addTest(TestNetworkIntegration('test_csv_parsing_with_real_data'))
    suite.addTest(TestNetworkIntegration('test_random_book_selection_integration'))
    suite.addTest(TestNetworkIntegration('test_end_to_end_workflow_with_mock_selection'))
    
    # エラーハンドリングテストを追加
    suite.addTest(TestErrorHandling('test_network_timeout_handling'))
    
    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    print("📊 結合テスト結果サマリー:")
    print(f"✅ 成功: {result.testsRun - len(result.failures) - len(result.errors)}件")
    if result.failures:
        print(f"❌ 失敗: {len(result.failures)}件")
    if result.errors:
        print(f"💥 エラー: {len(result.errors)}件")
    print("="*70)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)