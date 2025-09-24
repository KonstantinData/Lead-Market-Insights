"""
Test module for SMTP configuration and EmailAgent functionality.
"""
import os
import unittest
from unittest.mock import patch, MagicMock
import sys

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.config import SMTPConfig, get_smtp_config
from agents.email_agent import EmailAgent


class TestSMTPConfig(unittest.TestCase):
    """Test SMTP configuration loading from environment variables."""
    
    def setUp(self):
        """Set up test environment variables."""
        self.test_env_vars = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'test@example.com',
            'SMTP_PASS': 'test-password',
            'SMTP_SECURE': 'false',
            'MAIL_FROM': 'test@example.com'
        }
    
    def test_smtp_config_from_env(self):
        """Test loading SMTP configuration from environment variables."""
        with patch.dict(os.environ, self.test_env_vars):
            config = SMTPConfig()
            self.assertEqual(config.host, 'smtp.test.com')
            self.assertEqual(config.port, 587)
            self.assertEqual(config.user, 'test@example.com')
            self.assertEqual(config.password, 'test-password')
            self.assertEqual(config.secure, False)
            self.assertEqual(config.mail_from, 'test@example.com')
    
    def test_smtp_config_missing_required_vars(self):
        """Test error handling for missing required environment variables."""
        incomplete_env = self.test_env_vars.copy()
        del incomplete_env['SMTP_HOST']
        
        with patch.dict(os.environ, incomplete_env, clear=True):
            with self.assertRaises(ValueError) as cm:
                SMTPConfig()
            self.assertIn('SMTP_HOST', str(cm.exception))
    
    def test_smtp_config_bool_conversion(self):
        """Test boolean conversion for SMTP_SECURE."""
        test_cases = [
            ('true', True),
            ('True', True),
            ('1', True),
            ('yes', True),
            ('false', False),
            ('False', False),
            ('0', False),
            ('no', False),
            ('', True)  # default value
        ]
        
        for secure_value, expected in test_cases:
            env_vars = self.test_env_vars.copy()
            env_vars['SMTP_SECURE'] = secure_value
            
            with patch.dict(os.environ, env_vars):
                config = SMTPConfig()
                self.assertEqual(config.secure, expected, 
                               f"Failed for SMTP_SECURE='{secure_value}'")
    
    def test_smtp_config_int_conversion(self):
        """Test integer conversion for SMTP_PORT."""
        test_cases = [
            ('587', 587),
            ('465', 465),
            ('25', 25),
            ('', 587),  # default value
            ('invalid', 587)  # fallback to default
        ]
        
        for port_value, expected in test_cases:
            env_vars = self.test_env_vars.copy()
            env_vars['SMTP_PORT'] = port_value
            
            with patch.dict(os.environ, env_vars):
                config = SMTPConfig()
                self.assertEqual(config.port, expected,
                               f"Failed for SMTP_PORT='{port_value}'")


class TestEmailAgent(unittest.TestCase):
    """Test EmailAgent with environment configuration."""
    
    def setUp(self):
        """Set up test environment variables."""
        self.test_env_vars = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'test@example.com',
            'SMTP_PASS': 'test-password',
            'SMTP_SECURE': 'false',
            'MAIL_FROM': 'test@example.com'
        }
    
    @patch('smtplib.SMTP')
    def test_email_agent_from_env(self, mock_smtp):
        """Test EmailAgent creation from environment variables."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        with patch.dict(os.environ, self.test_env_vars):
            agent = EmailAgent.from_env()
            
            # Test that agent is configured correctly
            self.assertEqual(agent.smtp_server, 'smtp.test.com')
            self.assertEqual(agent.smtp_port, 587)
            self.assertEqual(agent.username, 'test@example.com')
            self.assertEqual(agent.password, 'test-password')
            self.assertEqual(agent.secure, False)
            self.assertEqual(agent.sender_email, 'test@example.com')
            
            # Test sending email
            result = agent.send_email('recipient@example.com', 'Test', 'Body')
            self.assertTrue(result)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with('test@example.com', 'test-password')


if __name__ == '__main__':
    unittest.main()