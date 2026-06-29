"""LLM configuration tab."""
from __future__ import annotations
import asyncio
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QLineEdit, QDoubleSpinBox, QSlider, QPushButton, QHBoxLayout, QLabel,
    QTextEdit, QDialog, QDialogButtonBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from ...utils.config_loader import get_config, save_config
from ...utils.prompts import _DEFAULT_SYSTEM_PROMPT
from ...llm.llm_factory import PROVIDER_DEFAULTS, PROVIDER_LABELS, fetch_models, create_llm_client

logger = logging.getLogger("BurgerRelay.llmtab")


class _PromptDialog(QDialog):
    """Modal dialog for editing the full system prompt."""

    def __init__(self, prompt_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑系统提示词")
        self.resize(700, 550)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        warning = QLabel(
            "⚠️ 非专业人员请勿修改！改动可能导致游戏指令解析异常。\n"
            "如不确定，点击「恢复默认」即可还原。")
        warning.setStyleSheet("color: #e5c07b; font-weight: bold; padding: 8px; "
                              "background: #2a2a1a; border-radius: 4px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        self._editor = QTextEdit()
        self._editor.setPlainText(prompt_text)
        self._editor.setStyleSheet(
            "QTextEdit { background: #FFFAF5; color: #5D4037; "
            "border: 1px solid #E8C9A0; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; }")
        layout.addWidget(self._editor)

        btn_box = QDialogButtonBox()
        btn_reset = QPushButton("🔄 恢复默认")
        btn_reset.clicked.connect(lambda: self._editor.setPlainText(_DEFAULT_SYSTEM_PROMPT))
        btn_box.addButton(btn_reset, QDialogButtonBox.ActionRole)
        btn_box.addButton(QDialogButtonBox.Ok)
        btn_box.addButton(QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def prompt_text(self) -> str:
        return self._editor.toPlainText()


class _ModelFetchThread(QThread):
    """Fetches model list from provider API in a background thread."""
    models_ready = pyqtSignal(list)
    fetch_failed = pyqtSignal(str)

    def __init__(self, provider: str, api_base: str, api_key: str = "") -> None:
        super().__init__()
        self._provider = provider
        self._api_base = api_base
        self._api_key = api_key

    def run(self) -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            models = loop.run_until_complete(
                fetch_models(self._provider, self._api_base, self._api_key))
            loop.close()
            self.models_ready.emit(models)
        except Exception as e:
            self.fetch_failed.emit(str(e))


class _TestThread(QThread):
    """Runs an LLM generate() call in a background thread."""
    test_done = pyqtSignal(str)   # result text
    test_error = pyqtSignal(str)  # error message

    def __init__(self, provider: str, model: str, api_base: str,
                 api_key: str = "", temperature: float = 0.1,
                 timeout: float = 5.0, max_tokens: int = 300,
                 input_text: str = "") -> None:
        super().__init__()
        self._provider = provider
        self._model = model
        self._api_base = api_base
        self._api_key = api_key
        self._temperature = temperature
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._input = input_text

    def run(self) -> None:
        try:
            client = create_llm_client(
                self._provider, self._model, self._api_base,
                self._api_key, self._temperature, self._timeout,
                self._max_tokens,
            )
            if client is None:
                self.test_error.emit(f"不支持的服务商: {self._provider}")
                return

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(client.generate(self._input))
            loop.close()

            if result and result != "{}":
                self.test_done.emit(result)
            elif result:
                # result is "{}" or similar — model got called but returned nothing useful
                self.test_error.emit(
                    "模型未返回有效指令（LLM 可能把输入判定为 ignore 或返回了空内容）"
                )
            else:
                self.test_error.emit("模型返回为空，请检查 API Key 和模型名称")
        except Exception as e:
            self.test_error.emit(str(e))


class LLMTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fetch_thread: _ModelFetchThread | None = None
        self._test_thread: _TestThread | None = None
        self._last_provider = ""
        self._system_prompt_text: str = _DEFAULT_SYSTEM_PROMPT
        self._loading = False  # suppress signals during load_config
        self._setup_ui()
        self._connect_signals()
        self.load_config()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ---- Model service ----
        svc = QGroupBox("模型服务")
        sf = QFormLayout(svc)

        self._provider = QComboBox()
        self._provider.addItem("🖥 本地 (Ollama)", "local")
        self._provider.addItem("☁️ 自定义 (OpenAI 兼容)", "custom")
        sf.addRow("服务商:", self._provider)

        # Model: editable combo + refresh button + status
        model_row = QHBoxLayout()
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.setMinimumWidth(200)
        self._model_combo.setPlaceholderText("选择或输入模型名")
        model_row.addWidget(self._model_combo)
        self._btn_refresh = QPushButton("🔄 刷新")
        self._btn_refresh.setToolTip("从 API 获取可用模型列表")
        model_row.addWidget(self._btn_refresh)
        sf.addRow("模型名称:", model_row)
        self._model_status = QLabel("")
        self._model_status.setStyleSheet("color: #8D6E63; font-size: 11px;")
        sf.addRow("", self._model_status)

        self._api_base = QLineEdit()
        self._api_base.setPlaceholderText("http://localhost:11434/api/generate")
        sf.addRow("API地址:", self._api_base)

        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.Password)
        self._api_key.setPlaceholderText("(可选)")
        sf.addRow("API Key:", self._api_key)

        self._timeout = QDoubleSpinBox()
        self._timeout.setRange(0.5, 30.0)
        self._timeout.setValue(5.0)
        self._timeout.setSuffix(" 秒")
        sf.addRow("超时:", self._timeout)

        from PyQt5.QtWidgets import QSpinBox
        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(50, 4096)
        self._max_tokens.setValue(300)
        self._max_tokens.setToolTip("越大回复越完整，但更慢")
        sf.addRow("最大 Token:", self._max_tokens)

        self._temperature = QSlider(Qt.Horizontal)
        self._temperature.setRange(0, 100)
        self._temperature.setValue(10)
        self._temp_label = QLabel("0.10")
        self._temperature.valueChanged.connect(lambda v: self._temp_label.setText(f"{v / 100:.2f}"))
        h = QHBoxLayout()
        h.addWidget(self._temperature)
        h.addWidget(self._temp_label)
        sf.addRow("温度:", h)
        layout.addWidget(svc)

        # ---- Test ----
        test = QGroupBox("测试大模型")
        tf = QVBoxLayout(test)
        self._test_input = QLineEdit()
        self._test_input.setPlaceholderText("输入测试弹幕，如：来一个肉饼加芝士")
        self._test_btn = QPushButton("测试发送")
        self._test_result = QLabel("")
        tf.addWidget(self._test_input)
        tf.addWidget(self._test_btn)
        tf.addWidget(self._test_result)
        layout.addWidget(test)

        # ---- System prompt ----
        prompt_grp = QGroupBox("系统提示词")
        pf_layout = QVBoxLayout(prompt_grp)
        btn_row = QHBoxLayout()
        self._btn_edit_prompt = QPushButton("📝 编辑系统提示词")
        self._btn_edit_prompt.setToolTip("打开提示词编辑器")
        btn_row.addWidget(self._btn_edit_prompt)
        self._prompt_warning = QLabel(
            "⚠️ 非专业人员请勿修改，改动可能导致指令解析异常")
        self._prompt_warning.setStyleSheet("color: #e5c07b; font-size: 11px;")
        btn_row.addWidget(self._prompt_warning)
        btn_row.addStretch()
        pf_layout.addLayout(btn_row)
        layout.addWidget(prompt_grp)

        layout.addStretch()

    def _connect_signals(self) -> None:
        self._btn_refresh.clicked.connect(self._on_refresh)
        self._btn_edit_prompt.clicked.connect(self._on_edit_prompt)
        self._test_btn.clicked.connect(self._on_test)
        self._test_input.returnPressed.connect(self._on_test)
        self._provider.currentTextChanged.connect(self._on_provider_changed)
        self._api_base.textChanged.connect(self._on_api_base_changed)

    # ---- Config load / save ----

    def load_config(self) -> None:
        self._loading = True
        try:
            cfg = get_config().get("llm", {})
            provider = cfg.get("provider", "custom")
            # Backward compat: migrate old provider names
            if provider in ("ollama", "openai", "deepseek", "azure"):
                provider = "local" if provider == "ollama" else "custom"
            idx = self._provider.findData(provider)
            if idx >= 0:
                self._provider.setCurrentIndex(idx)
            self._last_provider = provider

            saved_model = cfg.get("model", "")
            self._model_combo.clear()
            # Pre-populate defaults for this provider
            for m in PROVIDER_DEFAULTS.get(provider, []):
                self._model_combo.addItem(m)
            if saved_model:
                # Set current text to saved model (may not be in list)
                idx = self._model_combo.findText(saved_model)
                if idx >= 0:
                    self._model_combo.setCurrentIndex(idx)
                else:
                    self._model_combo.setCurrentText(saved_model)

            self._api_base.setText(cfg.get("api_base", ""))
            self._api_key.setText(cfg.get("api_key", ""))
            self._timeout.setValue(cfg.get("timeout", 5.0))
            self._max_tokens.setValue(cfg.get("max_tokens", 300))
            self._temperature.setValue(int(cfg.get("temperature", 0.1) * 100))
            self._system_prompt_text = cfg.get("system_prompt", "") or _DEFAULT_SYSTEM_PROMPT
        finally:
            self._loading = False

    def save_config(self) -> None:
        cfg = get_config()
        cfg["llm"]["provider"] = self._provider.currentData()
        cfg["llm"]["model"] = self._model_combo.currentText()
        cfg["llm"]["api_base"] = self._api_base.text()
        cfg["llm"]["api_key"] = self._api_key.text()
        cfg["llm"]["timeout"] = self._timeout.value()
        cfg["llm"]["max_tokens"] = self._max_tokens.value()
        cfg["llm"]["temperature"] = self._temperature.value() / 100
        cfg["system_prompt"] = getattr(self, "_system_prompt_text", _DEFAULT_SYSTEM_PROMPT)
        save_config(cfg)

    # ---- LLM Test ----

    def _on_test(self) -> None:
        text = self._test_input.text().strip()
        if not text:
            self._test_result.setText("❌ 请输入测试内容")
            self._test_result.setStyleSheet("color: #e5c07b;")
            return

        self._test_result.setText("⏳ 请求中...")
        self._test_result.setStyleSheet("color: #8D6E63;")
        self._test_btn.setEnabled(False)

        provider = self._provider.currentData()
        model = self._model_combo.currentText()
        api_base = self._api_base.text().strip()
        api_key = self._api_key.text()

        if self._test_thread and self._test_thread.isRunning():
            self._test_thread.terminate()
            self._test_thread.wait(1000)

        self._test_thread = _TestThread(
            provider=provider,
            model=model,
            api_base=api_base,
            api_key=api_key,
            temperature=self._temperature.value() / 100,
            timeout=self._timeout.value(),
            max_tokens=self._max_tokens.value(),
            input_text=text,
        )
        self._test_thread.test_done.connect(self._on_test_done)
        self._test_thread.test_error.connect(self._on_test_error)
        self._test_thread.finished.connect(lambda: self._test_btn.setEnabled(True))
        self._test_thread.start()

    def _on_test_done(self, result: str) -> None:
        self._test_result.setText(f"✅ {result}")
        self._test_result.setStyleSheet("color: #98c379;")

    def _on_test_error(self, error: str) -> None:
        # Make common errors readable
        if "401" in error or "Unauthorized" in error:
            msg = "❌ API Key 无效或未设置"
        elif "Connection" in error or "connect" in error:
            msg = "❌ 无法连接 API 服务器"
        elif "timeout" in error.lower():
            msg = "❌ 请求超时"
        else:
            msg = f"❌ {error}"
        self._test_result.setText(msg)
        self._test_result.setStyleSheet("color: #e06c75;")

    # ---- Prompt editor ----

    def _on_edit_prompt(self) -> None:
        dlg = _PromptDialog(self._system_prompt_text, self)
        if dlg.exec_() == QDialog.Accepted:
            self._system_prompt_text = dlg.prompt_text()
            # Persist immediately
            cfg = get_config()
            cfg["system_prompt"] = self._system_prompt_text
            save_config(cfg)
            logger.info("System prompt updated (%d chars)", len(self._system_prompt_text))

    # ---- Model fetching ----

    def _on_refresh(self) -> None:
        self._fetch_models()

    def _on_provider_changed(self, provider: str) -> None:
        if self._loading:
            return
        self._last_provider = provider
        # Clear and pre-populate defaults immediately
        current = self._model_combo.currentText()
        self._model_combo.clear()
        for m in PROVIDER_DEFAULTS.get(provider, []):
            self._model_combo.addItem(m)
        # Try to select something reasonable
        if current and self._model_combo.findText(current) >= 0:
            self._model_combo.setCurrentText(current)
        elif self._model_combo.count() > 0:
            self._model_combo.setCurrentIndex(0)
        # Auto-fetch
        self._fetch_models()

    def _on_api_base_changed(self, _text: str) -> None:
        # Don't auto-fetch on every keystroke; just on explicit refresh
        pass

    def _fetch_models(self) -> None:
        api_base = self._api_base.text().strip()
        if not api_base:
            self._model_status.setText("请先填写 API 地址")
            return

        self._model_status.setText("⏳ 获取中...")
        self._btn_refresh.setEnabled(False)

        provider = self._provider.currentData()
        api_key = self._api_key.text()
        # Cancel any in-flight fetch
        if self._fetch_thread and self._fetch_thread.isRunning():
            self._fetch_thread.terminate()
            self._fetch_thread.wait(1000)

        self._fetch_thread = _ModelFetchThread(provider, api_base, api_key)
        self._fetch_thread.models_ready.connect(self._on_models_ready)
        self._fetch_thread.fetch_failed.connect(self._on_fetch_failed)
        self._fetch_thread.finished.connect(lambda: self._btn_refresh.setEnabled(True))
        self._fetch_thread.start()

    def _on_models_ready(self, models: list[str]) -> None:
        current = self._model_combo.currentText()
        self._model_combo.clear()
        for m in models:
            self._model_combo.addItem(m)
        if current and self._model_combo.findText(current) >= 0:
            self._model_combo.setCurrentText(current)
        elif self._model_combo.count() > 0:
            self._model_combo.setCurrentIndex(0)
        self._model_status.setText(f"✅ 获取到 {len(models)} 个模型")

    def _on_fetch_failed(self, error: str) -> None:
        # Make common errors more readable
        if "401" in error:
            msg = "❌ 需要有效 API Key 才能获取模型列表"
        elif "403" in error:
            msg = "❌ API Key 无权限"
        elif "Cannot connect" in error or "Connection" in error:
            msg = "❌ 无法连接 API 服务器，请检查地址"
        else:
            msg = f"❌ 获取失败: {error}"
        self._model_status.setText(msg)
        logger.warning(f"Model fetch failed: {error}")
