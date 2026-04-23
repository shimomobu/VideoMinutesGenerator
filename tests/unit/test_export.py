"""TASK-06-01: Markdown 出力（write_markdown）のテスト"""
from pathlib import Path

import pytest

from vmg.export import OutputError, write_markdown


class TestWriteMarkdown:
    def test_returns_path(self, tmp_path):
        """戻り値が Path オブジェクトであること"""
        result = write_markdown("# 議事録\n", job_id="job_001", output_dir=tmp_path)
        assert isinstance(result, Path)

    def test_file_is_created(self, tmp_path):
        """minutes.md ファイルが作成されること"""
        result = write_markdown("# 議事録\n", job_id="job_001", output_dir=tmp_path)
        assert result.exists()
        assert result.name == "minutes.md"

    def test_output_path_structure(self, tmp_path):
        """出力パスが {output_dir}/{job_id}/minutes.md であること"""
        result = write_markdown("# 議事録\n", job_id="job_abc", output_dir=tmp_path)
        assert result == tmp_path / "job_abc" / "minutes.md"

    def test_content_preserved(self, tmp_path):
        """ファイル内容が正しく書き出されること"""
        content = "# 議事録\n\n## 1. 会議情報\n- 会議名: テスト\n"
        result = write_markdown(content, job_id="job_001", output_dir=tmp_path)
        assert result.read_text(encoding="utf-8") == content

    def test_first_line_is_heading(self, tmp_path):
        """書き出したファイルの先頭行が '# 議事録' であること"""
        content = "# 議事録\n\n## 2. 会議要約\n"
        result = write_markdown(content, job_id="job_001", output_dir=tmp_path)
        assert result.read_text(encoding="utf-8").splitlines()[0] == "# 議事録"

    def test_output_dir_created_automatically(self, tmp_path):
        """存在しない出力ディレクトリが自動作成されること"""
        new_base = tmp_path / "does_not_exist_yet"
        result = write_markdown("# 議事録\n", job_id="job_001", output_dir=new_base)
        assert result.parent.exists()

    def test_nested_output_dir_created(self, tmp_path):
        """ネストした出力ディレクトリも自動作成されること"""
        nested = tmp_path / "a" / "b" / "c"
        result = write_markdown("# 議事録\n", job_id="job_001", output_dir=nested)
        assert result.exists()

    def test_output_error_on_permission_denied(self, tmp_path):
        """書き込み権限なし時に OutputError が発生すること"""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)
        try:
            with pytest.raises(OutputError):
                write_markdown("# 議事録\n", job_id="job_001", output_dir=readonly_dir)
        finally:
            readonly_dir.chmod(0o755)

    def test_accepts_str_output_dir(self, tmp_path):
        """output_dir に文字列を渡しても動作すること"""
        result = write_markdown("# 議事録\n", job_id="job_001", output_dir=str(tmp_path))
        assert result.exists()
