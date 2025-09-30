import app
import config


def main() -> None:
    print("启动 IndexTTS2 简化界面...")
    status = app.refresh_api_status()
    print(status)

    app.demo.launch(
        server_name=config.APP_HOST,
        server_port=config.APP_PORT,
        share=config.APP_SHARE,
        inbrowser=True,
    )


if __name__ == "__main__":
    main()
