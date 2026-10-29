from PySide6.QtCore import QCoreApplication
from backend.mod_manager import ModListModel, ModProxyModel
from models.mod import Mod


def test_source_filter_combines_with_status_and_search():
    app = QCoreApplication.instance() or QCoreApplication([])
    model = ModListModel()
    model.set_mods([
        Mod('web-on', 'Online Active', 'Author', source='web:online', enabled=True),
        Mod('web-off', 'Online Inactive', 'Author', source='web:other', enabled=False),
        Mod('manual', 'Manual Active', 'Author', source='import', enabled=True),
        Mod('unknown', 'Unknown', 'Author', enabled=True),
    ])
    proxy = ModProxyModel()
    proxy.setSourceModel(model)
    assert proxy.sourceFilter == 'all' and proxy.rowCount() == 4
    proxy.sourceFilter = 'discover'
    assert proxy.rowCount() == 2
    proxy.filterMode = 'enabled'
    assert proxy.rowCount() == 1
    assert proxy.index(0, 0).data(ModListModel.IdRole) == 'web-on'
    proxy.sourceFilter = 'manual'
    assert proxy.rowCount() == 1
    assert proxy.index(0, 0).data(ModListModel.IdRole) == 'manual'
    proxy.searchText = 'Online'
    assert proxy.rowCount() == 0
    proxy.sourceFilter = 'all'
    assert proxy.rowCount() == 1
    proxy.searchText = ''
    proxy.filterMode = 'all'
    assert proxy.rowCount() == 4
    proxy.sourceFilter = 'invalid'
    assert proxy.sourceFilter == 'all' and proxy.rowCount() == 4
