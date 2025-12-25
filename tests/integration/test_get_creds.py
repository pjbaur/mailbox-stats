"""Integration tests for get_creds() function."""

import pytest
from unittest.mock import Mock, patch, mock_open
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import gmail_stats


def test_get_creds_from_cache(mocker):
    """Test loading valid cached credentials."""
    mock_creds = Mock(spec=Credentials)
    mock_creds.valid = True

    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        return_value=mock_creds
    )

    result = gmail_stats.get_creds()

    assert result == mock_creds
    # Should not trigger refresh or OAuth flow
    mock_creds.refresh.assert_not_called()


def test_get_creds_expired_with_refresh(mocker):
    """Test refreshing expired token."""
    mock_creds = Mock(spec=Credentials)
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh_token"
    mock_creds.to_json.return_value = '{"token": "data"}'

    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        return_value=mock_creds
    )
    mock_file = mocker.mock_open()
    mocker.patch("builtins.open", mock_file)

    result = gmail_stats.get_creds()

    mock_creds.refresh.assert_called_once()
    assert result == mock_creds
    # Verify file was opened for writing
    mock_file.assert_called_with("token.json", "w", encoding="utf-8")


def test_get_creds_no_cache_runs_oauth(mocker):
    """Test OAuth flow on missing token."""
    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        side_effect=FileNotFoundError
    )

    mock_flow = Mock(spec=InstalledAppFlow)
    mock_creds = Mock(spec=Credentials)
    mock_creds.to_json.return_value = '{"token": "new"}'
    mock_flow.run_local_server.return_value = mock_creds

    mocker.patch(
        "gmail_stats.InstalledAppFlow.from_client_secrets_file",
        return_value=mock_flow
    )
    mock_file = mocker.mock_open()
    mocker.patch("builtins.open", mock_file)

    result = gmail_stats.get_creds()

    assert result == mock_creds
    mock_flow.run_local_server.assert_called_once_with(port=0)
    mock_file.assert_called_with("token.json", "w", encoding="utf-8")


def test_get_creds_corrupted_token_runs_oauth(mocker):
    """Test OAuth flow on corrupted token."""
    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        side_effect=ValueError("Invalid JSON")
    )

    mock_flow = Mock(spec=InstalledAppFlow)
    mock_creds = Mock(spec=Credentials)
    mock_creds.to_json.return_value = '{"token": "new"}'
    mock_flow.run_local_server.return_value = mock_creds

    mocker.patch(
        "gmail_stats.InstalledAppFlow.from_client_secrets_file",
        return_value=mock_flow
    )
    mock_file = mocker.mock_open()
    mocker.patch("builtins.open", mock_file)

    result = gmail_stats.get_creds()

    assert result == mock_creds
    mock_flow.run_local_server.assert_called_once()


def test_get_creds_missing_client_secret(mocker):
    """Test error when client_secret.json missing."""
    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        side_effect=FileNotFoundError
    )
    mocker.patch(
        "gmail_stats.InstalledAppFlow.from_client_secrets_file",
        side_effect=FileNotFoundError("client_secret.json not found")
    )

    with pytest.raises(FileNotFoundError):
        gmail_stats.get_creds()


def test_get_creds_writes_token_on_refresh(mocker):
    """Test token.json is written on refresh."""
    mock_creds = Mock(spec=Credentials)
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh_token"
    mock_creds.to_json.return_value = '{"token": "data"}'

    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        return_value=mock_creds
    )

    mock_file = mocker.mock_open()
    mocker.patch("builtins.open", mock_file)

    gmail_stats.get_creds()

    # Verify write was attempted
    mock_file.assert_called_with("token.json", "w", encoding="utf-8")
    # Verify content was written
    handle = mock_file()
    handle.write.assert_called_with('{"token": "data"}')


def test_get_creds_expired_no_refresh_token(mocker):
    """Test OAuth flow when refresh token missing."""
    mock_creds = Mock(spec=Credentials)
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = None

    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        return_value=mock_creds
    )

    mock_flow = Mock(spec=InstalledAppFlow)
    mock_new_creds = Mock(spec=Credentials)
    mock_new_creds.to_json.return_value = '{"token": "new"}'
    mock_flow.run_local_server.return_value = mock_new_creds

    mocker.patch(
        "gmail_stats.InstalledAppFlow.from_client_secrets_file",
        return_value=mock_flow
    )
    mock_file = mocker.mock_open()
    mocker.patch("builtins.open", mock_file)

    result = gmail_stats.get_creds()

    assert result == mock_new_creds
    mock_flow.run_local_server.assert_called_once()


def test_get_creds_timing_logged(mocker, caplog):
    """Test timing is logged."""
    import logging
    caplog.set_level(logging.INFO)

    mock_creds = Mock(spec=Credentials)
    mock_creds.valid = True

    mocker.patch(
        "gmail_stats.Credentials.from_authorized_user_file",
        return_value=mock_creds
    )

    gmail_stats.get_creds()

    assert "elapsed=" in caplog.text
    assert "source=cache" in caplog.text
