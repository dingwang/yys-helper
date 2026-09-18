import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from PySide6.QtWidgets import QApplication
from yys_helper.ui.task_center import TaskCenterPage
from yys_helper.infrastructure.repository import AppRepository


class TaskCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_search_and_activity_configuration_persist(self):
        repo = AppRepository(':memory:')
        page = TaskCenterPage(repo)
        page.search.setText('首领')
        self.assertEqual(1, page.task_list.count())
        self.assertEqual('event_boss', page.selected_task.id)
        page.fields['title'].setText('月海试炼')
        page.rounds.setValue(12)
        page.save_settings()
        other = TaskCenterPage(repo)
        other.search.setText('首领')
        self.assertEqual(('月海试炼',), other.current_profile().title)
        self.assertEqual(12, other.rounds.value())
        page.close()
        other.close()
        repo.close()

    def test_active_task_freezes_settings_and_progress_is_visible(self):
        page = TaskCenterPage()
        page.set_connected(True)
        page.risk_ack.setChecked(True)
        page.set_task_active(True)
        self.assertFalse(page.start_button.isEnabled())
        self.assertFalse(page.rounds.isEnabled())
        self.assertFalse(page.task_list.isEnabled())
        page.update_progress('battle', 3, 64)
        self.assertIn('3', page.status.text())
        self.assertIn('战斗', page.status.text())
        page.set_task_active(False)
        self.assertTrue(page.start_button.isEnabled())
        page.close()

    def test_start_requires_connection_and_valid_activity_title(self):
        page = TaskCenterPage()
        page.risk_ack.setChecked(True)
        self.assertFalse(page.start_button.isEnabled())
        page.set_connected(True)
        self.assertTrue(page.start_button.isEnabled())
        page.search.setText('单关')
        self.assertFalse(page.start_button.isEnabled())
        page.fields['title'].setText('月海试炼')
        self.assertTrue(page.start_button.isEnabled())
        page.fields['title'].clear()
        self.assertFalse(page.start_button.isEnabled())
        page.close()

    def test_saved_excessive_duration_is_clamped_and_pace_persists(self):
        repo = AppRepository(':memory:')
        repo.set_setting('task_minutes', '720')
        page = TaskCenterPage(repo)
        self.assertEqual(120, page.minutes.value())
        page.pace_mode.setCurrentIndex(1)
        page.save_settings()
        other = TaskCenterPage(repo)
        self.assertEqual('relaxed', other.pace_mode.currentData())
        page.close()
        other.close()
        repo.close()

    def test_live_stop_controls_only_enabled_during_session(self):
        page = TaskCenterPage()
        self.assertFalse(page.stop_button.isEnabled())
        page.set_task_active(True)
        self.assertTrue(page.stop_button.isEnabled())
        self.assertTrue(page.finish_button.isEnabled())
        page.update_activity('resting', 25)
        self.assertIn('25', page.activity_label.text())
        page.set_task_active(False)
        self.assertFalse(page.finish_button.isEnabled())
        page.close()
