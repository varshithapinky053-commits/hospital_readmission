CREATE TABLE IF NOT EXISTS users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(100) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    full_name   VARCHAR(150) NOT NULL,
    role        VARCHAR(50)  NOT NULL DEFAULT 'staff',
    email       VARCHAR(150),
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login  DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS patients (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    patient_id          VARCHAR(50)  NOT NULL UNIQUE,
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    date_of_birth       DATE         NOT NULL,
    gender              VARCHAR(20)  NOT NULL,
    phone               VARCHAR(30),
    email               VARCHAR(150),
    address             TEXT,
    insurance_type      VARCHAR(50),
    primary_diagnosis   VARCHAR(150),
    medical_specialty   VARCHAR(100),
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS predictions (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    patient_id          VARCHAR(50) NOT NULL,
    time_in_hospital    INT         NOT NULL,
    num_lab_procedures  INT         NOT NULL,
    num_procedures      INT         NOT NULL,
    num_medications     INT         NOT NULL,
    num_outpatient      INT         NOT NULL,
    num_inpatient       INT         NOT NULL,
    num_emergency       INT         NOT NULL,
    readmission_risk    DECIMAL(5,1) NOT NULL,
    risk_level          VARCHAR(20)  NOT NULL,
    predicted_by        INT,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (predicted_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS audit_log (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT,
    action      VARCHAR(100) NOT NULL,
    details     TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_patients_patient_id ON patients(patient_id);
CREATE INDEX idx_predictions_patient_id ON predictions(patient_id);
CREATE INDEX idx_predictions_created_at ON predictions(created_at);
