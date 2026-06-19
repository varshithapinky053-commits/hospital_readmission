-- Hospital Readmission System - MySQL Configuration
-- Run manually or via init_db(): mysql -u root -p < config.sql

CREATE DATABASE IF NOT EXISTS hospital
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE hospital;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 1;
