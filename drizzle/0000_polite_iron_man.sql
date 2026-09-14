CREATE TABLE `homes` (
	`id` text PRIMARY KEY NOT NULL,
	`invite_hash` text,
	`invite_expires` integer
);
--> statement-breakpoint
CREATE TABLE `photos` (
	`id` text PRIMARY KEY NOT NULL,
	`home_id` text NOT NULL,
	`mime` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `records` (
	`home_id` text NOT NULL,
	`kind` text NOT NULL,
	`id` text NOT NULL,
	`payload` text NOT NULL,
	`version` integer DEFAULT 1 NOT NULL,
	PRIMARY KEY(`home_id`, `kind`, `id`)
);
--> statement-breakpoint
CREATE TABLE `sessions` (
	`hash` text PRIMARY KEY NOT NULL,
	`home_id` text NOT NULL,
	`member` text NOT NULL,
	`expires` integer NOT NULL
);
