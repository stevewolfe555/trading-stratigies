<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Add asset_type column to symbols table.
     *
     * This enables multi-asset trading support:
     * - stock: Traditional stocks (NASDAQ, NYSE, LSE)
     * - binary_option: Binary options (Polymarket)
     * - crypto: Cryptocurrencies (future)
     * - forex: Foreign exchange (future)
     * - commodity: Commodities (future)
     */
    public function up(): void
    {
        Schema::table('symbols', function (Blueprint $table) {
            $table->string('asset_type', 20)->default('stock')->after('exchange');
            $table->index('asset_type');
        });

        // Update existing symbols to 'stock' (explicit for clarity)
        DB::statement("UPDATE symbols SET asset_type = 'stock' WHERE asset_type IS NULL");
    }

    /**
     * Reverse the migration.
     */
    public function down(): void
    {
        Schema::table('symbols', function (Blueprint $table) {
            $table->dropIndex(['asset_type']);
            $table->dropColumn('asset_type');
        });
    }
};
