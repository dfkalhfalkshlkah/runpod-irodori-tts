# RunPod Irodori TTS Worker 設計

## 目的

Irodori TTS を RunPod Serverless のキュー型エンドポイントとして公開し、同期APIで音声を生成できる独立した公開リポジトリを提供する。RunPod Hub の審査・ビルド・テストに必要なファイルを揃え、利用者が作成者個人のGitHubリポジトリを参照せずにデプロイできる状態にする。

## 対象範囲

- RunPod Serverless Worker
- Irodori TTS APIの起動処理
- RunPod Hub用メタデータと動作確認用リクエスト
- ローカルで実行できる単体テスト
- ビルド、デプロイ、API入出力を説明するREADME
- MIT License

APIクライアント、デスクトップアプリ、利用者のRunPod APIキー管理、RunPod Endpointの課金管理は含めない。

## リポジトリ構成

```text
runpod-irodori-tts/
├── .runpod/
│   ├── hub.json
│   └── tests.json
├── docs/superpowers/specs/
│   └── 2026-07-16-runpod-irodori-tts-design.md
├── tests/
│   └── test_handler.py
├── .dockerignore
├── .gitignore
├── Dockerfile
├── Dockerfile.publish
├── LICENSE
├── README.md
├── handler.py
├── requirements.txt
└── start.sh
```

## 実行構成

Dockerイメージは`docker.io/katalive/irodori-tts:latest`を基盤として使用する。Worker固有のPython依存関係を明示的にインストールし、`start.sh`をコンテナの起動コマンドにする。RunPod Hubが認証情報なしでビルドできるように、基盤イメージは公開状態を維持する。初回公開または基盤イメージ更新時は`Dockerfile.publish`を使用し、上流のIrodori TTS APIイメージから直接ビルドする。これにより通常の`Dockerfile`が自分自身の未公開イメージを参照する循環を避ける。

`start.sh`は次の順序で処理する。

1. Irodori TTS APIを`127.0.0.1:8880`で起動する。
2. ヘルスチェックを繰り返し、モデルの読み込み完了を待つ。
3. 制限時間内に起動しなければコンテナをエラー終了する。
4. APIが利用可能になったらRunPod Workerをフォアグラウンドで起動する。
5. Worker終了時にはIrodori TTS APIのプロセスも終了する。

## API入出力

WorkerはRunPodのジョブ形式を受け取る。

```json
{
  "input": {
    "input": "こんにちは",
    "voice": "none",
    "response_format": "wav",
    "irodori": {
      "num_steps": 16,
      "seed": 42
    }
  }
}
```

`input.input`を必須の音声合成テキストとして扱う。`irodori.num_steps`と`irodori.seed`は省略可能とし、安全な範囲の整数だけを受け付ける。`ref_wav_b64`が指定された場合はBase64を検証し、一時ファイルとしてアップロードした後、成功・失敗にかかわらず削除する。

成功時は次の形式を返す。

```json
{
  "audio_b64": "Base64で符号化したWAVデータ",
  "mime_type": "audio/wav"
}
```

入力不備または上流APIの失敗時は、秘密情報や音声データをログへ出さず、`error`を含むJSONを返す。

## RunPod Hub設定

`.runpod/hub.json`では次を設定する。

- 種別: Serverless
- カテゴリー: Audio
- 実行環境: GPU 1基
- 16 GB以上のGPUプール
- Queue型Endpoint
- コンテナディスク: 5 GB以上。基盤イメージの実容量に応じて検証時に増やす
- Irodori TTSの事前読み込み、CUDA、bf16に関する既定環境変数

`.runpod/tests.json`では短い日本語を入力し、WorkerがRunPodの制限時間内に正常終了することを確認する。RunPod HubのテストはHTTP成功を確認するため、音声内容の詳細検証は単体テストで補う。

## エラー処理

- 空文字、型違い、範囲外の推論設定を合成前に拒否する。
- 不正なBase64は上流APIへ送信しない。
- ヘルスチェックと音声合成には個別のタイムアウトを設ける。
- 参照音声のアップロード失敗を無視せず、明示的なエラーにする。
- 一時ファイルは`finally`相当の処理で必ず削除する。
- エラーメッセージは応答本文を一定の長さに制限し、認証情報を含めない。

## 検証

次の確認を実施する。

1. Pythonの構文検査
2. モック化したIrodori TTS APIに対する単体テスト
3. Shellスクリプトの構文検査
4. `hub.json`と`tests.json`のJSON構文検査
5. Dockerイメージのビルド
6. 生成イメージの設定と起動コマンドの確認
7. GitHubへpush後、公開リポジトリのファイル一覧、既定ブランチ、コミット作成者情報を確認

GPUを必要とする実際の音声生成は、RunPod Hubへの申請前にRunPod Endpoint上で確認する。

## 公開情報と履歴

- 既存の他リポジトリをForkせず、空のリポジトリに新しい履歴を作成する。
- README、Dockerラベル、Git履歴に個人のGitHub URLや個人メールアドレスを含めない。
- 外部プロジェクトは一般公開されている正式名称とURLだけを記載する。
- APIキー、アクセストークン、Endpoint IDなどの秘密情報をコミットしない。
