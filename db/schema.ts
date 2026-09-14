import {sqliteTable,text,integer,primaryKey,index} from 'drizzle-orm/sqlite-core';
export const homes=sqliteTable('homes',{id:text('id').primaryKey(),inviteHash:text('invite_hash'),inviteExpires:integer('invite_expires')});
export const sessions=sqliteTable('sessions',{hash:text('hash').primaryKey(),homeId:text('home_id').notNull(),member:text('member').notNull(),expires:integer('expires').notNull()});
export const records=sqliteTable('records',{homeId:text('home_id').notNull(),kind:text('kind').notNull(),id:text('id').notNull(),payload:text('payload').notNull(),version:integer('version').notNull().default(1)},t=>[primaryKey({columns:[t.homeId,t.kind,t.id]})]);
export const photos=sqliteTable('photos',{id:text('id').primaryKey(),homeId:text('home_id').notNull(),mime:text('mime').notNull()});
