-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS `chat_with_pdf` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user if it doesn't exist
CREATE USER IF NOT EXISTS 'chat_user'@'%' IDENTIFIED BY 'chat_password';

-- Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON `chat_with_pdf`.* TO 'chat_user'@'%' WITH GRANT OPTION;

-- Apply changes
FLUSH PRIVILEGES;
