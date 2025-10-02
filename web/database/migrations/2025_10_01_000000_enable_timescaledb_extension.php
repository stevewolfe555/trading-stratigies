<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement('CREATE EXTENSION IF NOT EXISTS timescaledb;');
    }

    public function down(): void
    {
        // Do not drop the extension automatically
    }
};
