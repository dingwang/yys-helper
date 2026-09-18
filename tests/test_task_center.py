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
