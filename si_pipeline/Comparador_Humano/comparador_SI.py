import pandas as pd
import os
from loguru import logger

def comparador_SI():
    """Enhanced SI comparison with comprehensive logging for debugging."""
    old_file = 'Comparador_Humano/exceles/Asegurados_SI_old.xlsx'
    new_file = 'Comparador_Humano/exceles/Asegurados_SI.xlsx'
    output_file = 'Comparador_Humano/exceles/comparison_result.xlsx'

    logger.info("🔍 Starting SI file comparison with enhanced logging...")
    
    # Check if files exist
    logger.info(f"📁 Checking file existence:")
    logger.info(f"   Old file: {old_file} - {'✅ EXISTS' if os.path.exists(old_file) else '❌ MISSING'}")
    logger.info(f"   New file: {new_file} - {'✅ EXISTS' if os.path.exists(new_file) else '❌ MISSING'}")
    
    if not os.path.exists(old_file):
        logger.error(f"❌ Old file not found: {old_file}")
        return False
        
    if not os.path.exists(new_file):
        logger.error(f"❌ New file not found: {new_file}")
        return False
    
    # Check file sizes
    old_size = os.path.getsize(old_file)
    new_size = os.path.getsize(new_file)
    logger.info(f"📊 File sizes:")
    logger.info(f"   Old file: {old_size:,} bytes")
    logger.info(f"   New file: {new_size:,} bytes")
    
    try:
        # Load the two Excel files
        logger.info("📖 Loading Excel files...")
        old_df = pd.read_excel(old_file)
        logger.info(f"✅ Old file loaded: {len(old_df)} rows, {len(old_df.columns)} columns")
        logger.info(f"   Columns: {list(old_df.columns)}")
        
        new_df = pd.read_excel(new_file)
        logger.info(f"✅ New file loaded: {len(new_df)} rows, {len(new_df.columns)} columns")
        logger.info(f"   Columns: {list(new_df.columns)}")
        
        # Check if CODIGO_INFOPLAN column exists
        if 'CODIGO_INFOPLAN' not in old_df.columns:
            logger.error(f"❌ CODIGO_INFOPLAN column not found in old file. Available columns: {list(old_df.columns)}")
            return False
            
        if 'CODIGO_INFOPLAN' not in new_df.columns:
            logger.error(f"❌ CODIGO_INFOPLAN column not found in new file. Available columns: {list(new_df.columns)}")
            return False
        
        # Show sample data
        logger.info("📋 Sample data from old file (first 5 rows):")
        for i, row in old_df.head().iterrows():
            logger.info(f"   Row {i}: CODIGO_INFOPLAN = {row.get('CODIGO_INFOPLAN', 'N/A')}")
        
        logger.info("📋 Sample data from new file (first 5 rows):")
        for i, row in new_df.head().iterrows():
            logger.info(f"   Row {i}: CODIGO_INFOPLAN = {row.get('CODIGO_INFOPLAN', 'N/A')}")
        
        # Clean and prepare data for comparison
        logger.info("🧹 Cleaning and preparing data for comparison...")
        old_codes = old_df['CODIGO_INFOPLAN'].astype(str).str.strip()
        new_codes = new_df['CODIGO_INFOPLAN'].astype(str).str.strip()
        
        logger.info(f"📊 Unique codes in old file: {old_codes.nunique()}")
        logger.info(f"📊 Unique codes in new file: {new_codes.nunique()}")
        
        # Find new records (in new_df but not in old_df)
        logger.info("🔍 Finding new records...")
        new_mask = ~new_codes.isin(old_codes)
        new_records = new_df[new_mask]
        new_records = new_records.drop_duplicates(subset='CODIGO_INFOPLAN')
        
        # Find removed records (in old_df but not in new_df)  
        logger.info("🔍 Finding removed records...")
        removed_mask = ~old_codes.isin(new_codes)
        removed_records = old_df[removed_mask]
        removed_records = removed_records.drop_duplicates(subset='CODIGO_INFOPLAN')

        # Detailed logging of results
        logger.info(f"📊 Comparison Results:")
        logger.info(f"   🆕 New records found: {len(new_records)}")
        logger.info(f"   ❌ Removed records found: {len(removed_records)}")
        
        if len(new_records) > 0:
            logger.info("📋 Sample new records:")
            for i, (idx, row) in enumerate(new_records.head().iterrows()):
                logger.info(f"   New record {i+1}: CODIGO_INFOPLAN = {row.get('CODIGO_INFOPLAN', 'N/A')}")
        
        if len(removed_records) > 0:
            logger.info("📋 Sample removed records:")
            for i, (idx, row) in enumerate(removed_records.head().iterrows()):
                logger.info(f"   Removed record {i+1}: CODIGO_INFOPLAN = {row.get('CODIGO_INFOPLAN', 'N/A')}")

        # Export comparison result
        logger.info(f"💾 Saving comparison results to: {output_file}")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with pd.ExcelWriter(output_file) as writer:
            new_records.to_excel(writer, sheet_name='New in New File', index=False)
            removed_records.to_excel(writer, sheet_name='Missing in New File', index=False)

        logger.info(f"✅ Comparison results saved successfully")
        
        # Check output file
        if os.path.exists(output_file):
            output_size = os.path.getsize(output_file)
            logger.info(f"📊 Output file size: {output_size:,} bytes")
            
            # Verify the saved data
            try:
                test_df = pd.read_excel(output_file, sheet_name='New in New File')
                logger.info(f"✅ Verification: Output file contains {len(test_df)} new records")
            except Exception as e:
                logger.warning(f"⚠️ Could not verify output file: {e}")
        else:
            logger.error(f"❌ Output file was not created: {output_file}")

        # Replace the old file with the new one
        logger.info("🔄 Replacing old file with new file...")
        try:
            # Create backup of old file before replacement
            backup_file = old_file.replace('.xlsx', '_backup.xlsx')
            if os.path.exists(old_file):
                os.rename(old_file, backup_file)
                logger.info(f"📦 Backup created: {backup_file}")
            
            # Move new file to old file location
            os.rename(new_file, old_file)
            logger.info(f"✅ '{new_file}' replaced '{old_file}' for next comparison")
            
            # Verify the replacement
            if os.path.exists(old_file):
                new_old_size = os.path.getsize(old_file)
                logger.info(f"✅ Replacement verified. New old file size: {new_old_size:,} bytes")
            else:
                logger.error(f"❌ File replacement failed - old file not found after replacement")
                
        except Exception as e:
            logger.error(f"❌ Error during file replacement: {e}")
            return False
        
        logger.info("✅ SI comparison completed successfully")
        return True, len(new_records), len(removed_records)
        
    except Exception as e:
        logger.error(f"❌ Error during SI comparison: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

# Run the function
#comparador_SI()
