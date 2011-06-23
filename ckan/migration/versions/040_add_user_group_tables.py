from migrate import *

def upgrade(migrate_engine):
    migrate_engine.execute('''

BEGIN;

CREATE TABLE "member" (
    id text NOT NULL,
    user_id text,
    group_id text,
    capacity text,
    "state" text, 
    revision_id text 
);

CREATE TABLE member_revision ( 
    id text NOT NULL, 
    user_id text, 
    group_id text, 
    capacity text, 
    "state" text, 
    revision_id text NOT NULL, 
    continuity_id text, 
    expired_id text, 
    revision_timestamp timestamp without time zone, 
    expired_timestamp timestamp without time zone, 
    "current" boolean 
); 
 

ALTER TABLE "group"
    ADD COLUMN parent_id text;

ALTER TABLE group_revision
    ADD COLUMN parent_id text;

ALTER TABLE package_group
    ADD COLUMN capacity text,
    ADD COLUMN type text;

ALTER TABLE package_group_revision
    ADD COLUMN capacity text,
    ADD COLUMN type text;

ALTER TABLE "member"
    ADD CONSTRAINT member_pkey PRIMARY KEY (id);

ALTER TABLE "member"
    ADD CONSTRAINT member_group_id_fkey FOREIGN KEY (group_id) REFERENCES "group"(id);

ALTER TABLE "member"
    ADD CONSTRAINT member_user_id_fkey FOREIGN KEY (user_id) REFERENCES "user"(id);

ALTER TABLE "member" 
    ADD CONSTRAINT member_revision_id_fkey FOREIGN KEY (revision_id) REFERENCES revision(id); 

ALTER TABLE member_revision 
    ADD CONSTRAINT member_revision_pkey PRIMARY KEY (id, revision_id); 
 
ALTER TABLE member_revision 
    ADD CONSTRAINT member_revision_continuity_id_fkey FOREIGN KEY (continuity_id) REFERENCES member(id); 
 
ALTER TABLE member_revision 
    ADD CONSTRAINT member_revision_group_id_fkey FOREIGN KEY (group_id) REFERENCES "group"(id); 
 
ALTER TABLE member_revision 
    ADD CONSTRAINT member_revision_revision_id_fkey FOREIGN KEY (revision_id) REFERENCES revision(id); 
 
ALTER TABLE member_revision 
    ADD CONSTRAINT member_revision_user_id_fkey FOREIGN KEY (user_id) REFERENCES "user"(id); 

COMMIT;
''')
