DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `userId` bigint(20) NOT NULL,
  `objectionConfig` text,
  PRIMARY KEY (`userId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

