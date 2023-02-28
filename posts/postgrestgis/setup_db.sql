-- create schema for a toy database
create schema api;
-- a little housekeeping
drop table if exists plot;
create extension if not exists postgis;
-- define the table schema
create table api.plot (
    id serial primary key,
    lon real not null,
    lat real not null,
    geom geometry(Point, 4326)
);
--- add data (random points from a large bounding box)
insert into api.plot (lon, lat)
select random() * (-57.2183 - (-131.3702)) + -131.3702,
    random() * (51.5376 - 11.9402) + 11.9402
from generate_series(1, 1000);
--- update geom column values
update api.plot
set geom = st_setsrid(st_makepoint(lon, lat), 4326);
--- add spatial index
alter table api.plot create index if not exists idx_plot_geom on api.plot using gist(geom);
--- create roles for postgrest access
create role web_anon nologin;
grant usage on schema api to web_anon;
grant select on api.plot to web_anon;
create role authenticator noinherit login password 'mysecretpassword';
grant web_anon to authenticator;
--- function for querying plots by bounding box
create function api.query_bbox(xmin real, xmax real, ymin real, ymax real) returns setof api.plot as $$
select *
from api.plot
where st_contains(
        st_makeenvelope(
            query_bbox.xmin,
            query_bbox.xmax,
            query_bbox.ymin,
            query_bbox.ymax,
            4326
        ),
        plot.geom::geometry
    );
$$ stable language sql;