PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS beds (
    bed_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    bed_label VARCHAR(50) NOT NULL,
    occupied_by_tenant_id INTEGER,
    is_available BOOLEAN DEFAULT 1,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE CASCADE,
    FOREIGN KEY (occupied_by_tenant_id) REFERENCES tenants(tenant_id) ON DELETE SET NULL,
    UNIQUE (room_id, bed_label)
);
